"""\
Purpose: Define reusable SIP Flows
Initial Version: Costas Skarakis 5/25/2021
"""
from time import sleep


def basic_call_monitored_events(A, B, duration=2):
    """ Basic CSTA Call flow between two CSTA Monitored Endpoints
    SIP flow must be handled elsewhere.
    SIP_A calls SIP_B. B answers. SIP_A hangs up after the duration.
    CSTA Users A, B will receive the corresponding CSTA events

    :A: The caller (CstaUser instance)
    :B: The callee (CstaUser instance)
    :duration: The duration of the call
    """
    Aside = ["ServiceInitiatedEvent", "OriginatedEvent", "DeliveredEvent", "EstablishedEvent",
             "ConnectionClearedEvent"]
    Bside = ["DeliveredEvent", "EstablishedEvent", "ConnectionClearedEvent"]

    A.wait_for_message("ServiceInitiatedEvent")
    A.wait_for_message("OriginatedEvent")
    A.wait_for_message("DeliveredEvent")
    A.wait_for_message("EstablishedEvent")

    B.wait_for_message("DeliveredEvent")
    B.wait_for_message("EstablishedEvent")

    sleep(duration)

    B.wait_for_message("ConnectionClearedEvent")

    A.wait_for_message("ConnectionClearedEvent")
