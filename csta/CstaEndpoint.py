"""\
Purpose: Simulate a CSTA device
Initial Version: Costas Skarakis 29/4/2019  
"""
import os
from _socket import timeout

from common import util
from common.client import TCPClient
from csta.CstaMessage import xmlpath
from sip.SipEndpoint import SipEndpoint
from csta.CstaParser import parseBytes as parseBytes_csta, buildMessageFromFile
import sip.SipFlows as SipFlows


def get_xml(name):
    return os.path.join(xmlpath, name)


class CstaEndpoint(SipEndpoint):
    """
    SipEndpoint with CSTA capabilities
    """

    def __init__(self, directory_number):
        super().__init__(directory_number)
        self.csta_links = []
        self.incoming_event_threads = []
        self.event_id = 1
        self.last_sent_csta_message = None

    def sip_connect(self, local_address, destination_address, protocol="tcp"):
        """ Wrap SipEndpoint.connect with a different name """
        return self.connect(local_address, destination_address, protocol)

    def csta_connect(self, destination_address):
        """ Connect to CSTA Server """
        if not "source_ip" in self.parameters:
            raise Exception("Must connect SIP first")
        local_ip = self.parameters["source_ip"]
        dest_ip, dest_port = destination_address
        # Only TCP implemented
        # 0 means bind to any available local port
        csta_link = TCPClient(local_ip, 0)
        self.csta_links.append(csta_link)
        csta_link.connect(dest_ip, dest_port)

        inBytes = csta_link.waitForData()
        req = parseBytes_csta(inBytes)

        resp = buildMessageFromFile(get_xml("SystemStatusResponse.xml"), self.parameters, eventid=req.eventid)
        csta_link.send(resp.contents())

        reg = buildMessageFromFile(get_xml("SystemRegister.xml"), self.parameters, eventid=0)
        csta_link.send(reg.contents())

        inBytes = csta_link.waitForData()
        reg_resp = parseBytes_csta(inBytes)
        assert reg_resp.event == "SystemRegisterResponse", 'Tried to start a new dialog with a SIP Response'
        return csta_link

    def monitor_start(self):
        """ Connect a CSTA client link, send MonitorStart """
        csta_link = self.csta_links[0]
        m = buildMessageFromFile(get_xml("MonitorStart.xml"), self.parameters, eventid=1)
        csta_link.send(m.contents())
        in_bytes = csta_link.waitForData()
        inmessage = parseBytes_csta(in_bytes)
        assert inmessage.event == "MonitorStartResponse", "Sent:{}  Received:{}".format(m.event, str(inmessage))

    def start_new_incoming_event_thread(self, csta_link=None, role=None):
        """ Start a new thread to wait for incoming CSTA events

        :role optional argument that can be used to impose certain checks on incoming messages
            Possible values: 1) Any of "originator", "initiator", "A", "Aside", "caller" or
                             2) Any of "destination", "target", "B", "Bside", "callee"

            If any of the group 1) role is selected the incoming messages will be checked to be in the following order:
              "ServiceInitiatedEvent", "OriginatedEvent", "DeliveredEvent", "EstablishedEvent","ConnectionClearedEvent"

            If any of the group 2) role is selected the incoming messages will be checked to be in the following order:
              "DeliveredEvent", "EstablishedEvent", "ConnectionClearedEvent"

            If no role is selected there will be no checks for incoming csta messages

            TODO: Add support for custom message ordering check
        """
        if not csta_link:
            csta_link = self.csta_links[0]
        self.incoming_event_threads.append(util.serverThread(self.wait_for_csta_events,
                                                             csta_link,
                                                             role))

    def wait_for_csta_events(self, csta_link, assert_leg=None):
        """ Waits for CSTA messages until the CSTA link is not valid """

        if assert_leg in ("originator", "initiator", "A", "Aside", "caller"):
            assert_message_queue = ["ServiceInitiatedEvent", "OriginatedEvent", "DeliveredEvent", "EstablishedEvent",
                                    "ConnectionClearedEvent"]
        elif assert_leg in ("destination", "target", "B", "Bside", "callee"):
            assert_message_queue = ["DeliveredEvent", "EstablishedEvent", "ConnectionClearedEvent"]
        else:
            assert_message_queue = []

        # reset_queue = assert_message_queue[:]

        while self.csta_links:
            # Close and unset csta_link to stop the thread
            try:
                in_bytes = csta_link.waitForCstaData(timeout=1.0)
                inmessage = parseBytes_csta(in_bytes)
                # if assert_leg and not assert_message_queue:
                    # Reset queue in case it needs to be reused
                    # assert_message_queue = reset_queue[:]
                if assert_message_queue:
                    expected_event = assert_message_queue.pop(0)
                    assert inmessage.event == expected_event, \
                        "User {} expected {} but got {}".format(self.parameters["user"], expected_event,
                                                                inmessage.event)
                # print("User:{} received {}".format(user,inmessage))
            except timeout:
                pass

    def send_new_sip(self, target_sip_ep=None, message_string="", expected_response=None, ignore_messages=()):
        """ Wrapper for SipEndpoint.send_new. Starts a new SIP dialog and send a SIP Request """
        return self.send_new(target_sip_ep, message_string, expected_response, ignore_messages)

    def send_sip(self, message_string="", expected_response=None, ignore_messages=(), dialog=None):
        """ Wrapper for SipEndpoint.send. Send a SIP message within an existing SIP dialog """
        return self.send(message_string, expected_response, ignore_messages, dialog)

    def reply_sip(self, message_string, dialog=None):
        """ Wrapper for SipEndpoint.reply Send a response to a previously received message """
        return self.reply(message_string, dialog)

    def send_csta(self, message_xml_file):
        """ Send a CSTA request
        :message_xml_file: The type of request. There should be a matching filename in csta/xml
        """
        m = buildMessageFromFile(get_xml(message_xml_file), self.parameters, self.event_id)
        self.last_sent_csta_message = m
        self.csta_links[0].send(m.contents())
        self.event_id += 1

    def waitForCstaMessage(self, message_type, ignore_messages=()):
        inmessage = None
        while not inmessage or inmessage.event in ignore_messages:
            in_bytes = self.csta_links[0].waitForData()
            inmessage = parseBytes_csta(in_bytes)
        assert inmessage.event == message_type, \
            '{}: Got "{}" while expecting "{}"'.format(self.number, inmessage.event, message_type)
        assert inmessage.eventid == self.event_id, \
            '{}: Wrong event id received: {}. \n' \
            'Last message sent: \n{}' \
            '\nMessage received:\n{}\n'.format(self.number,
                                               inmessage.event,
                                               self.last_sent_csta_message,
                                               inmessage)
        return inmessage

    def unregister(self):
        """ Unregister SIP and stop all incoming CSTA event threads """
        SipFlows.unregister(self)
        for csta_link in self.csta_links:
            csta_link.socket.close()
        self.csta_links = []
        for thread in self.incoming_event_threads:
            thread.result()
