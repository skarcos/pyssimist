"""\
Purpose:
Initial Version: Costas Skarakis 7/11/2020  
"""
import threading
from datetime import datetime
from itertools import cycle

from common import util
from common.server import CstaServer
from csta.CstaApplication import CstaApplication
import time


def handle_make_call(csta_server, make_call_message):
    # https://wiki.unify.com/images/3/3e/CSTA_introduction_and_overview.pdf
    userA = csta_server.get_user(make_call_message["callingDevice"])
    userB = csta_server.get_user(make_call_message["calledDirectoryNumber"])
    print("in", userA.number, userB.number)
    # Although user A sent MakeCall from the client application, this will arrive in the
    # corresponding userA in the server, for who this will be an incoming transaction
    userA.update_incoming_transactions(make_call_message)
    csta_server.send("MakeCallResponse", to_user=userA)
    print("Sent MakeCallResponse to", userB.number)
    userA.set_parameter("initiatingDevice", userA.number)
    userA.set_parameter("localConnectionInfo", "initiated")
    userA.set_parameter("networkCallingDevice", userA.number)
    userA.set_parameter("networkCalledDevice", userB.number)
    userA.set_parameter("cause", "makeCall")
    csta_server.send("ServiceInitiatedEvent", to_user=userA)

    # phone A is calling
    print(userA.number, "is calling")
    userA.set_parameter("callingDevice", userA.number)
    userA.set_parameter("calledDevice", userB.number)
    csta_server.send("OriginatedEvent", to_user=userA)

    # phone B is ringing
    print(userB.number, "is ringing")
    userA.set_parameter("localConnectionInfo", "connected")
    userA.set_parameter("cause", "newCall")
    userA.set_parameter("alertingDevice", userB.number)
    userA.set_parameter("deviceIdentifier", userB.number)
    userA.set_parameter("numberDialed", userB.number)
    csta_server.send("DeliveredEvent", to_user=userA)

    userB.set_parameter("localConnectionInfo", "alerting")
    userB.set_parameter("alertingDevice", userB.number)
    userB.set_parameter("deviceIdentifier", userB.number)
    userB.set_parameter("numberDialed", userB.number)
    userB.set_parameter("networkCallingDevice", userA.number)
    userB.set_parameter("networkCalledDevice", userB.number)
    userB.set_parameter("cause", "newCall")
    csta_server.send("DeliveredEvent", to_user=userB)

    # phone B answers
    print(userB.number, "answers")
    userA.set_parameter("answeringDevice", userB.number)
    csta_server.send("EstablishedEvent", to_user=userA)

    userB.set_parameter("localConnectionInfo", "connected")
    userB.set_parameter("callingDevice", userA.number)
    userB.set_parameter("calledDevice", userB.number)
    userB.set_parameter("answeringDevice", userB.number)
    csta_server.send("EstablishedEvent", to_user=userB)

    csta_server.calls.append((userA, userB))


def handle_clear_connection(csta_server, message):
    cause = message["cause"]
    # https://wiki.unify.com/images/3/3e/CSTA_introduction_and_overview.pdf
    userA = csta_server.get_user(message["deviceID"])
    # phone A or B hangs up after call_duration seconds
    userA.set_parameter("releasingDevice", userA.number)
    userA.set_parameter("cause", cause)
    userA.set_parameter("localConnectionInfo", "null")
    csta_server.send("ConnectionClearedEvent", to_user=userA)
    for call in csta_server.calls:
        if call[0] is userA:
            userB = call[1]
            userB.set_parameter("releasingDevice", userA.number)
            userA.set_parameter("cause", cause)
            userB.set_parameter("localConnectionInfo", "null")
            csta_server.send("ConnectionClearedEvent", to_user=userB)
            csta_server.calls.remove(call)

def make_call(application, monitored_users, call_duration):
    userA = application.get_user(next(monitored_users))
    userB = application.get_user(next(monitored_users))
    userA.send(to_user=userB, message="MakeCall")
    print("MakeCall", userA.number, userB.number, datetime.now())
    userA.wait_for_message("MakeCallResponse")
    print("MakeCallResponse", userA.number, userB.number, datetime.now())
    userA.wait_for_message("ServiceInitiatedEvent")
    userA.wait_for_message("OriginatedEvent")
    userA.wait_for_message("DeliveredEvent")
    userB.wait_for_message("DeliveredEvent")
    userA.wait_for_message("EstablishedEvent")
    userB.wait_for_message("EstablishedEvent")
    print(userA.number, userB.number, "talk for", call_duration, "seconds")
    # sleep always causes trouble
    time.sleep(call_duration)
    hangup(userA, userB)
    # threading.Timer(call_duration, hangup, (userA, userB)).start()


def hangup(userA, userB):
    print(userA.number, "hangs up")
    userA.set_parameter("reason", value="Because I wanted to hang up")
    userA.send(to_user=userB, message="ClearConnection")
    userA.wait_for_message("ConnectionClearedEvent")
    userB.wait_for_message("ConnectionClearedEvent")


def startup(application, users):
    for user in users:
        new_user = application.new_user(user)
        new_user.monitor_start()


def statistics(csta_server, application):
    while True:
        time.sleep(5)
        print(["{} in call with {}".format(call[0].number, call[1].number) for call in csta_server.calls])


if __name__ == "__main__":
    HOST, PORT = "localhost", 9999
    MockCSTATCP = CstaServer(HOST, PORT)
    MockCSTATCP.serve_in_background()
    MockCSTATCP.on("MakeCall", handle_make_call)
    MockCSTATCP.on("ClearConnection", handle_clear_connection)
    MockCSTATCP.calls = []  # will store active calls here
    A = CstaApplication()
    A.connect(("localhost", 0),
              (HOST, PORT),
              "tcp")
    statistics_thread = threading.Thread(target=statistics, args=(MockCSTATCP, A))
    statistics_thread.start()
    users = [str(i+1000) for i in range(20)]
    user_pool = cycle(users)
    startup(A, users)
    test = util.Load(make_call, A, user_pool, 4, duration=10, quantity=5, interval=1)
    test.start()
    test.monitor()
    MockCSTATCP.wait_shutdown()
