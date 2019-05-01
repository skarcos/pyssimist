"""\
Purpose: Functions for parsing CSTA messages and creating CstaMessage objects
Initial Version: Costas Skarakis 11/11/2018
"""
import re
import xml.etree.ElementTree as ET
from csta.CstaMessage import CstaMessage

ENCODING="utf8"

def buildMessageFromFile(filename,parameters,eventid):
    with open(filename,"r") as file:
        return buildMessage(file.read(),parameters,eventid)
        
def buildMessage(message,parameters,eventid):
    xml_encoding=re.search("encoding=[\'\"](.*)[\'\"] ?\?\>",message).group(1)
    tString=message.strip().format(**parameters)
    #bString=bytes(tString.replace("\n","\r\n")+2*"\r\n",encoding=xml_encoding)
    bString=bytes("%04d"%eventid+tString,encoding=xml_encoding)
    bHeader=bytes.fromhex("%08X"%(len(bString)+4))
    cstaMessage=parseBytes(bHeader+bString)
    return cstaMessage

def parseBytes(bString):
    xml_encoding=re.search(b"encoding=[\'\"](.*)[\'\"] ?\?\>",bString).group(1)
    encoding=xml_encoding.decode(encoding=ENCODING)
    header=bString[:8]
    try:
        body=bString[8:].strip().decode(encoding)
    except:
        print(bString)
        raise
    try:
        root=ET.fromstring(body)
    except:
        print(header)
        print(body)
        raise
    tree=ET.ElementTree(root)
    ns=re.search("^{(.*)}",root.tag)
    if ns:
        namespace=ns.group(1)
        cstamessage=CstaMessage(header,tree,encoding,namespace)        
    else:
        print("Warning: No namespace defined in message",root.tag)
        cstamessage=CstaMessage(header,tree,encoding)
    return cstamessage

if __name__=="__main__":
#    import os
#    os.chdir(r'.\CstaPool')
#    s=buildMessageFromFile("SystemRegister.xml",{"deviceID":10101001100,"reason":"because"},9999)
    a = b'\x00\x00\x03\xeb9999<?xml version="1.0" encoding="UTF-8"?><ServiceInitiatedEvent xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><monitorCrossRefID>1169730059</monitorCrossRefID><initiatedConnection><callID>FF000100000000002D65C85C1C750000</callID><deviceID>302118840100</deviceID></initiatedConnection><initiatingDevice><deviceIdentifier>N&lt;302118840100&gt;;noa=nk</deviceIdentifier></initiatingDevice><localConnectionInfo>initiated</localConnectionInfo><cause>makeCall</cause><servicesPermitted><callControlServices><clearConnection>true</clearConnection></callControlServices><callAssociatedServices/><mediaAttachementServices/><routeingServices/><voiceServices/></servicesPermitted><mediaCallCharacteristics><mediaClass><voice>true</voice><image>false</image><im>false</im></mediaClass></mediaCallCharacteristics><extensions><privateData><private xmlns:scx="http://www.siemens.com/schema/csta"><scx:extendedServicesPermitted/></private></privateData></extensions></ServiceInitiatedEvent>'
    b = b'\x00\x00\x04C9999<?xml version="1.0" encoding="UTF-8"?><OriginatedEvent xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><monitorCrossRefID>1169730059</monitorCrossRefID><originatedConnection><callID>FF000100000000002D65C85C1C750000</callID><deviceID>302118840100</deviceID></originatedConnection><callingDevice><deviceIdentifier>302118840100</deviceIdentifier></callingDevice><calledDevice><deviceIdentifier>N&lt;302118840101&gt;;displayNumber=302118840101;noa=nk</deviceIdentifier></calledDevice><localConnectionInfo>connected</localConnectionInfo><cause>newCall</cause><servicesPermitted><callControlServices><clearConnection>true</clearConnection></callControlServices><callAssociatedServices/><mediaAttachementServices/><routeingServices/><voiceServices/></servicesPermitted><mediaCallCharacteristics><mediaClass><voice>true</voice><image>false</image><im>false</im></mediaClass></mediaCallCharacteristics><extensions><privateData><private xmlns:scx="http://www.siemens.com/schema/csta"><scx:extendedServicesPermitted/></private></privateData></extensions></OriginatedEvent>'
    c = b'\x00\x00\x04A0002<?xml version="1.0" encoding="UTF-8"?><MakeCallResponse xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><callingDevice><callID>FF000100000000007778C95C05030000</callID><deviceID>302118840100</deviceID></callingDevice></MakeCallResponse>'
    m = parseBytes(c)
    print(m["deviceID"])
