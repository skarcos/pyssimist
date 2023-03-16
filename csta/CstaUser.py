"""\
Purpose: Simulate a CSTA User
Initial Version: Costas Skarakis 8/7/2020 (Aug 7)
"""
from common.tc_logging import warning, exception
from csta.CstaMessage import is_response, is_event, is_request
from threading import Lock, Event


class CstaUser:
    def __init__(self, number, csta_application):
        self.number = number
        self.busy = False
        self.csta_application = csta_application
        self.monitorCrossRefID = None
        self.callID = None
        self.calls = []  # store multiple callIDs
        # Transactions are a dictionary of eventid to request eg {353: "MakeCall"}
        self.inc_transactions = {}
        self.out_transactions = {}
        self.deviceID = number
        self.message_buffer = []
        self.buffer_event = Event()
        self.buffer_mod_time = None
        self.lock = Lock()
        self.parameters = {"monitorCrossRefID": self.monitorCrossRefID,
                           "CSTA_CREATE_MONITOR_CROSS_REF_ID": self.monitorCrossRefID,
                           "CSTA_USE_MONITOR_CROSS_REF_ID": self.monitorCrossRefID,
                           "callID": self.callID,
                           "deviceID": self.deviceID}

    def get_transaction_id(self, message):
        """ Determine what the correct eventID is for an outgoing message based on the current state and the message.
         EventID and transactionID can be called InvokeID sometimes, like... always"""
        if is_response(message):
            # make sure that this response belongs to an active transaction, for instance if MakeCallResponse is
            # received, make sure there is a MakeCall in our active transactions
            target_request = message.split("Response")[0]
            assert target_request in self.inc_transactions.values(), "{}: Refusing to send {} without having received "\
                                                                 "{} first".format(self.number,
                                                                                   message,
                                                                                   target_request)
            for eventid in self.inc_transactions:
                if self.inc_transactions[eventid] == target_request:
                    # to review if we need to handle parallel transactions of the same type
                    return eventid
        elif is_request(message):
            if not self.out_transactions:
                return self.csta_application.min_event_id
            else:
                return max(int(eventid) for eventid in self.out_transactions) + 1
        else:
            assert is_event(message), "Message {} is not a response, request or event".format(message)
            return 9999

    def update_outgoing_transactions(self, message):
        """ message is of type CstaMessage"""
        if message.is_response():
            if message.eventid in self.inc_transactions:
                self.inc_transactions.pop(message.eventid)
                self.csta_application.min_event_id = max(self.csta_application.min_event_id, message.eventid + 1)
        elif message.is_request():
            if message.eventid in self.out_transactions:
                warning("Sending request {0} with invokeid {1}, "
                        "although request {2} with invokeid {0} has not been answered".format(message.event,
                                                                                              message.eventid,
                                                                                              self.out_transactions[
                                                                                                  message.eventid]))
            self.out_transactions[message.eventid] = message.event
            self.csta_application.min_event_id = max(self.csta_application.min_event_id, message.eventid + 1)
        else:
            assert message.is_event(), "Message {} is not a response, request or event".format(message.event)

    def update_incoming_transactions(self, message):
        """ message is of type CstaMessage"""
        if message.is_response():
            if message.eventid in self.out_transactions:
                self.out_transactions.pop(message.eventid)
                self.csta_application.min_event_id = max(self.csta_application.min_event_id, message.eventid + 1)
            else:
                exception("{}: Received csta response {} with invoke id {} "
                          "but there is no matching active transaction:\n{}\n{}".format(self.number,
                                                                                     message.event,
                                                                                     message.eventid,
                                                                                     self.out_transactions,
                                                                                     message))
        elif message.is_request():
            if message.eventid in self.inc_transactions:
                warning("{0}: Received request {1} with invokeid {2}, while"
                        " request {3} with invokeid {2} is already active".format(self.number,
                                                                                  message.event,
                                                                                  message.eventid,
                                                                                  self.inc_transactions[message.eventid]))
            self.inc_transactions[message.eventid] = message.event
            self.csta_application.min_event_id = max(self.csta_application.min_event_id, message.eventid + 1)
        else:
            assert message.is_event(), "Message {} is not a response, request or event".format(message.event)

    def update_call_id(self, message):
        callID = message["callID"]
        if message["deviceID"] and callID:
            self.callID = callID
            if callID not in self.calls:
                self.calls.append(callID)
            self.set_parameter("callID", callID)

    def monitor_start(self):
        return self.csta_application.monitor_start(self.number)

    def set_parameter(self, key, value):
        self.parameters[key] = value

    def prepare_message(self, message):
        """
        Convert a SIP message string to SipMessage object

        :param message: The message string
        :return: A CstaMessage object
        """
        return self.csta_application.prepare_message(self.number, message)

    def send(self, message, to_user=None, callID=None):
        return self.csta_application.send(message, from_user=self.number, to_user=to_user, callID=callID)

    def wait_for_message(self, message, ignore_messages=(), timeout=5.0):
        return self.csta_application.wait_for_csta_message(self.number,
                                                           message,
                                                           ignore_messages=ignore_messages,
                                                           timeout=timeout)

    def reset(self):
        with self.lock:
            buffer = self.message_buffer
            self.message_buffer = []
            self.busy = False
            self.callID = None
            self.calls = []
            self.inc_transactions = {}
            self.out_transactions = {}
            self.buffer_mod_time = None
        return buffer
