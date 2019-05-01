"""\
Purpose: CSTA message object
Initial Version: Costas Skarakis 11/11/2018
"""
import os
import xml.etree.ElementTree as ET
import io

xmlpath = os.path.join(os.path.realpath(__file__).replace(os.path.basename(__file__), ''), "CstaPool")


class CstaMessage(object):
    """
    Representation of a CSTA message
    """

    def __init__(self, header, xml_tree, encoding="UTF-8",
                 namespace="http://www.ecma-international.org/standards/ecma-323/csta/ed4"):
        # s_ip,s_port,d_ip,d_port
        self.eventid = int(header[-4:])
        self.size = header[:4]
        self.header = header
        self.encoding = encoding
        self.body = xml_tree
        self.namespace = namespace
        self.root = self.body.getroot()
        self.event = self.root.tag.replace("{" + self.namespace + "}", '')
        ET.register_namespace("", self.namespace)

    def __getitem__(self, key):
        for tag in self.body.iter():
            element = tag.find("{" + self.namespace + "}" + key)
            if element is not None:
                break
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
        return repr(self)

    def message(self):
        return repr(self)

    def contents(self):
        """ returns byte string """
        # Recalculate length
        self.size = bytes.fromhex("%08X" % (len(self.message()) + 8))
        return self.size + \
               self.header[-4:] + \
               bytes(self.message(), encoding=self.encoding)


if __name__ == "__main__":
    pass
