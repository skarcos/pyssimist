"""\
Purpose:
Initial Version: Costas Skarakis 7/11/2020  
"""
from common.server import CstaServer
from csta.CstaApplication import CstaApplication
import time


def HandleMakeCall(csta_server, make_call_message, call_duration=1):
    # https://wiki.unify.com/images/3/3e/CSTA_introduction_and_overview.pdf
    userA = csta_server.get_user(make_call_message["callingDevice"])
    userB = csta_server.get_user(make_call_message["calledDirectoryNumber"])

    userA.wait_for_message("MakeCall")
    csta_server.send("MakeCallResponse", to_user=userA)

    userA.set_parameter("initiatingDevice", userA.number)
    userA.set_parameter("localConnectionInfo", "initiated")
    userA.set_parameter("networkCallingDevice", userA.number)
    userA.set_parameter("networkCalledDevice", userB.number)
    userA.set_parameter("cause", "makeCall")
    csta_server.send("ServiceInitiatedEvent", to_user=userA)

    # phone A is calling
    userA.set_parameter("callingDevice", userA.number)
    userA.set_parameter("calledDevice", userB.number)
    csta_server.send("OriginatedEvent", to_user=userA)

    # phone B is ringing
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
    userA.set_parameter("answeringDevice", userB.number)
    csta_server.send("EstablishedEvent", to_user=userA)

    userB.set_parameter("localConnectionInfo", "connected")
    userB.set_parameter("callingDevice", userA.number)
    userB.set_parameter("calledDevice", userB.number)
    userB.set_parameter("answeringDevice", userB.number)
    csta_server.send("EstablishedEvent", to_user=userB)

    # phone A or B hangs up after call_duration seconds
    time.sleep(call_duration)
    userA.set_parameter("releasingDevice", userA.number)
    userA.set_parameter("localConnectionInfo", "null")
    csta_server.send("ConnectionClearedEvent", to_user=userA)

    userB.set_parameter("releasingDevice", userA.number)
    userB.set_parameter("localConnectionInfo", "null")
    csta_server.send("ConnectionClearedEvent", to_user=userB)


def MakeCall(userA, userB, call_duration):
    userA.send(to_user=userB, message="MakeCall")
    userA.wait_for_message("MakeCallResponse")
    userA.wait_for_message("ServiceInitiatedEvent")
    userA.wait_for_message("OriginatedEvent")
    userA.wait_for_message("DeliveredEvent")
    userB.wait_for_message("DeliveredEvent")
    userA.wait_for_message("EstablishedEvent")
    userB.wait_for_message("EstablishedEvent")
    # call duration also set here to avoid timeouts
    time.sleep(call_duration)
    userA.wait_for_message("ConnectionClearedEvent")
    userB.wait_for_message("ConnectionClearedEvent")


if __name__ == "__main__":
    HOST, PORT = "localhost", 9999
    MockCSTATCP = CstaServer(HOST, PORT)
    MockCSTATCP.serve_in_background()
    MockCSTATCP.on("MakeCall", HandleMakeCall)
    A = CstaApplication()
    A.connect(("localhost", 0),
              (HOST, PORT),
              "tcp")
    u1000 = A.new_user("1000")
    u1001 = A.new_user("1001")
    u1000.monitor_start()
    u1001.monitor_start()
    MakeCall(u1000, u1001, call_duration=1)
    time.sleep(2)
    MockCSTATCP.shutdown()
