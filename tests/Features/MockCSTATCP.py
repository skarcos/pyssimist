"""\
Purpose:
Initial Version: Costas Skarakis 7/11/2020  
"""
from common.server import CstaServer
from csta.CstaApplication import CstaApplication
from csta.CstaEndpoint import CstaEndpoint
import time


def HandleMakeCall(csta_server, make_call_message, call_duration=1):
    # https://wiki.unify.com/images/3/3e/CSTA_introduction_and_overview.pdf
    userA = make_call_message["callingDevice"]
    userB = make_call_message["calledDirectoryNumber"]

    csta_server.send("MakeCallResponse", from_user=userA)

    csta_server.set_parameter(user=userA, key="initiatingDevice", value=userA)  # initiatingDevice/deviceIdentifier
    csta_server.set_parameter(user=userA, key="localConnectionInfo", value="initiated")  # localConnectionInfo
    csta_server.set_parameter(user=userA, key="networkCallingDevice", value=userA)  # networkCallingDevice/deviceIdentifier
    csta_server.set_parameter(user=userA, key="networkCalledDevice", value=userB)  # networkCalledDevice/deviceIdentifier
    csta_server.set_parameter(user=userA, key="cause", value="makeCall")  # cause
    csta_server.send("ServiceInitiatedEvent", from_user=userA)

    # phone A is calling
    csta_server.set_parameter(user=userA, key="callingDevice", value=userA)  # callingDevice/deviceIdentifier
    csta_server.set_parameter(user=userA, key="calledDevice", value=userB)  # calledDevice/deviceIdentifier
    csta_server.send("OriginatedEvent", from_user=userA)

    # phone B is ringing
    csta_server.set_parameter(user=userA, key="localConnectionInfo", value="connected")  # localConnectionInfo
    csta_server.set_parameter(user=userA, key="alertingDevice", value=userB)  # alertingDevice/deviceIdentifier
    csta_server.set_parameter(user=userA, key="deviceIdentifier", value=userB)  # calledDevice/deviceIdentifier
    csta_server.set_parameter(user=userA, key="numberDialed", value=userB)  # lastRedirectionDevice/numberDialed
    csta_server.set_parameter(user=userA, key="cause", value="newCall")  # cause
    csta_server.send("DeliveredEvent", from_user=userA)

    csta_server.set_parameter(user=userB, key="localConnectionInfo", value="alerting")  # localConnectionInfo
    csta_server.set_parameter(user=userB, key="alertingDevice", value=userB)  # alertingDevice/deviceIdentifier
    csta_server.set_parameter(user=userB, key="deviceIdentifier", value=userB)  # calledDevice/deviceIdentifier
    csta_server.set_parameter(user=userB, key="numberDialed", value=userB)  # lastRedirectionDevice/numberDialed
    csta_server.set_parameter(user=userB, key="cause", value="newCall")  # cause
    csta_server.set_parameter(user=userB, key="networkCallingDevice", value=userA)  # networkCallingDevice/deviceIdentifier
    csta_server.set_parameter(user=userB, key="networkCalledDevice", value=userB)  # networkCalledDevice/deviceIdentifier
    csta_server.send("DeliveredEvent", from_user=userB)

    # phone B answers
    csta_server.set_parameter(user=userA, key="answeringDevice", value=userB)  # answeringDevice/deviceIdentifier
    csta_server.send("EstablishedEvent", from_user=userA)

    csta_server.set_parameter(user=userB, key="answeringDevice", value=userB)  # answeringDevice/deviceIdentifier
    csta_server.set_parameter(user=userB, key="localConnectionInfo", value="connected")  # localConnectionInfo
    csta_server.set_parameter(user=userB, key="callingDevice", value=userA)  # callingDevice/deviceIdentifier
    csta_server.set_parameter(user=userB, key="calledDevice", value=userB)  # calledDevice/deviceIdentifier
    csta_server.send("EstablishedEvent", from_user=userB)

    # phone A or B hangs up after call_duration seconds
    time.sleep(call_duration)
    csta_server.set_parameter(user=userA, key="releasingDevice", value=userA)  # releasingDevice/deviceIdentifier
    csta_server.set_parameter(user=userA, key="localConnectionInfo", value="null")  # localConnectionInfo
    csta_server.send("ConnectionClearedEvent", from_user=userA)

    csta_server.set_parameter(user=userB, key="releasingDevice", value=userA)  # releasingDevice/deviceIdentifier
    csta_server.set_parameter(user=userB, key="localConnectionInfo", value="null")  # localConnectionInfo
    csta_server.send("ConnectionClearedEvent", from_user=userB)


def MakeCall(csta_application, userA, userB, call_duration):
    csta_application.send(from_user=userA, to_user=userB, message="MakeCall")
    csta_application.wait_for_csta_message(for_user=userA, message="MakeCallResponse", new_request=True)
    csta_application.wait_for_csta_message(for_user=userA, message="ServiceInitiatedEvent")
    csta_application.wait_for_csta_message(for_user=userA, message="OriginatedEvent")
    csta_application.wait_for_csta_message(for_user=userA, message="DeliveredEvent")
    csta_application.wait_for_csta_message(for_user=userB, message="DeliveredEvent")
    csta_application.wait_for_csta_message(for_user=userA, message="EstablishedEvent")
    csta_application.wait_for_csta_message(for_user=userB, message="EstablishedEvent")
    # call duration also set here to avoid timeouts
    time.sleep(call_duration)
    csta_application.wait_for_csta_message(for_user=userB, message="ConnectionClearedEvent")
    csta_application.wait_for_csta_message(for_user=userB, message="ConnectionClearedEvent")


if __name__ == "__main__":
    HOST, PORT = "localhost", 9999
    MockCSTATCP = CstaServer(HOST, PORT)
    MockCSTATCP.serve_in_background()
    MockCSTATCP.on("MakeCall", HandleMakeCall)
    A = CstaApplication()
    A.connect(("localhost", 0),
              (HOST, PORT),
              "tcp")
    A.monitor_start("1000")
    A.monitor_start("1001")
    MakeCall(A, "1000", "1001", call_duration=1)
    time.sleep(2)
    MockCSTATCP.shutdown()
