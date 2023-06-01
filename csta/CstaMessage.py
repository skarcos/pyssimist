"""\
Purpose: CSTA message object
Initial Version: Costas Skarakis 11/11/2018
"""
import os
import re
import xml.etree.ElementTree as ET
import io
from common import util

xmlpath = os.path.join(os.path.realpath(__file__).replace(os.path.basename(__file__), ''), "CstaPool")


def is_response(message):
    if message.endswith("Response"):
        return True
    else:
        return False


def is_request(message):
    if is_event(message) or is_response(message):
        return False
    else:
        return True


def is_event(message):
    return message.endswith("Event")


class CstaMessage(object):
    """
    Representation of a CSTA message
    """

    def __init__(self, header, body):
        # s_ip,s_port,d_ip,d_port
        self.eventid = int(header[-4:])
        self.size = header[:4]
        self.header = header
        self.encoding = body.encoding
        self.body = body
        self.root = body.root
        self.namespace = body.namespace
        self.event = body.event

    def is_response(self):
        return is_response(self.event)

    def is_request(self):
        return is_request(self.event)

    def is_event(self):
        return is_event(self.event)

    def find_element(self, key):
        """
        Obsolete. Kept for backwards compatibility
        :param key:
        :return:
        """
        element = None
        for tag in self.body.iter():
            element = tag.find(key)
            if element is None:
                element = tag.find("{" + self.namespace + "}" + key)
            if element is None:
                element_search = re.search(key, tag.tag)
                if element_search:
                    element = tag
            if element is not None:
                break
        return element

    def __getitem__(self, key):
        element = self.body.get_tag(key)
        if element is None:
            return None
        else:
            return element.text

    def __setitem__(self, key, value):
        element = self.body.get_tag(key)
        element.text = value

    def __repr__(self):
        return repr(self.body)

    def __str__(self):
        return repr(self)

    def message(self):
        return str(self)

    def set_eventid(self, eventid):
        self.header = self.header[:4] + bytes("%04d" % eventid, encoding=self.encoding)
        self.eventid = eventid

    def contents(self):
        """ returns byte string """
        # Recalculate length
        self.size = bytes.fromhex("%08X" % (len(self.message()) + 8))
        return self.size + \
               self.header[-4:] + \
               bytes(self.message(), encoding=self.encoding)


if __name__ == "__main__":
    print(is_response("GetAgentStateResponse"))
    print(is_request("GetAgentStateResponse"))