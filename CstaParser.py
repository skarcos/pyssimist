import re
import xml.etree.ElementTree as ET
from CstaMessage import CstaMessage

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
    import os
    os.chdir(r'.\CstaPool')
    s=buildMessageFromFile("SystemRegister.xml",{"deviceID":10101001100,"reason":"because"},9999)
