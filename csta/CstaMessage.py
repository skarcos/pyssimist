"""\
Purpose: CSTA message object
Initial Version: Costas Skarakis 11/11/2018
"""
import os
import re
import xml.etree.ElementTree as ET
import io

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

    def __init__(self, header, xml_tree, str_body=None, encoding="UTF-8",
                 ns=(("", "http://www.ecma-international.org/standards/ecma-323/csta/ed4"),)):
        # s_ip,s_port,d_ip,d_port
        self.eventid = int(header[-4:])
        self.size = header[:4]
        self.header = header
        self.encoding = encoding
        self.str_body = str_body
        self.body = xml_tree
        self.namespace = ""
        self.root = self.body.getroot()
        for namespace in ns:
            if not re.match(r"ns\d+", namespace[0]):
                # namespace is pair of (name, url)
                ET.register_namespace(*namespace)
            if namespace[0] == "":
                # default namespace
                self.namespace = namespace[1]
#        self.event = self.root.tag.replace("{" + self.namespace + "}", '')
        self.event = re.match(r"({.*})?(.*)", self.root.tag).group(2)

    def is_response(self):
        return is_response(self.event)

    def is_request(self):
        return is_request(self.event)

    def is_event(self):
        return is_event(self.event)

    def __getitem__(self, key):
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
        if element is None:
            return None
        else:
            return element.text

    def __setitem__(self, key, value):
        element = self.body.find("{" + self.namespace + "}" + key)
        element.text = value

    def __repr__(self):
        result = io.BytesIO()
        self.body.write(result,
                        xml_declaration=self.encoding,
                        encoding=self.encoding)
        result.flush()
        return result.getvalue().decode(encoding=self.encoding)

    def __str__(self):
        if self.str_body:
            return self.str_body
        else:
            return repr(self)

    def message(self):
        return str(self)

    def contents(self):
        """ returns byte string """
        # Recalculate length
        self.size = bytes.fromhex("%08X" % (len(self.message()) + 8))
        return self.size + \
               self.header[-4:] + \
               bytes(self.message(), encoding=self.encoding)


if __name__ == "__main__":
    pass
