"""\
Purpose: Functions for parsing CSTA messages and creating CstaMessage objects
Initial Version: Costas Skarakis 11/11/2018
"""
import re
import xml.etree.ElementTree as ET
from csta.CstaMessage import CstaMessage

ENCODING = "utf8"


def buildMessageFromFile(filename, parameters, eventid):
    with open(filename, "r") as file:
        return buildMessage(file.read(), parameters, eventid)


def buildMessage(message, parameters={}, eventid=0):
    encoding_search = re.search("encoding=[\'\"](\S*)[\'\"].* ?\?\>", message)
    if not encoding_search:
        print("Warning: No encoding defined in message:", message)
        xml_encoding = ENCODING
    else:
        xml_encoding = encoding_search.group(1)
    tString = message.strip().format(**parameters)
    # bString=bytes(tString.replace("\n","\r\n")+2*"\r\n",encoding=xml_encoding)
    bString = bytes("%04d" % eventid + tString, encoding=xml_encoding)
    bHeader = bytes.fromhex("%08X" % (len(bString) + 4))
    cstaMessage = parseBytes(bHeader + bString)
    return cstaMessage


def parseBytes(bString):
    try:
        xml_encoding = re.search(b"encoding=[\'\"](\S*)[\'\"].* ?\?\>", bString).group(1)
        encoding = xml_encoding.decode(encoding=ENCODING)
    except AttributeError:
        encoding = ENCODING
    header = bString[:8]
    try:
        body = bString[8:].strip().decode(encoding)
    except:
        print("Cannot decode CSTA message with ", encoding)
        print(bString)
        raise
    try:
        root = ET.fromstring(body)
    except:
        print("Cannot parse CSTA message string:")
        print(header)
        print(body)
        raise
    tree = ET.ElementTree(root)
    # ns=re.search("^{(.*)}",root.tag)
    XMLParser = ET.XMLPullParser(events=['start-ns'])
    XMLParser.feed(body)
    ns = [e[1] for e in XMLParser.read_events()]
    if ns:
        # namespace=ns.group(1)
        cstamessage = CstaMessage(header, tree, body, encoding=encoding, ns=ns)
    else:
        # print("Warning: No namespace defined in message",root.tag)
        cstamessage = CstaMessage(header, tree, body, encoding=encoding)
    return cstamessage


if __name__ == "__main__":
    #    import os
    #    os.chdir(r'.\CstaPool')
    #    s=buildMessageFromFile("SystemRegister.xml",{"deviceID":10101001100,"reason":"because"},9999)
    a = []
    b = []
    a.append(b'\x00\x00\x03\xeb9999<?xml version="1.0" encoding="UTF-8"?><ServiceInitiatedEvent xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><monitorCrossRefID>1169730059</monitorCrossRefID><initiatedConnection><callID>FF000100000000002D65C85C1C750000</callID><deviceID>302118840100</deviceID></initiatedConnection><initiatingDevice><deviceIdentifier>N&lt;302118840100&gt;;noa=nk</deviceIdentifier></initiatingDevice><localConnectionInfo>initiated</localConnectionInfo><cause>makeCall</cause><servicesPermitted><callControlServices><clearConnection>true</clearConnection></callControlServices><callAssociatedServices/><mediaAttachementServices/><routeingServices/><voiceServices/></servicesPermitted><mediaCallCharacteristics><mediaClass><voice>true</voice><image>false</image><im>false</im></mediaClass></mediaCallCharacteristics><extensions><privateData><private xmlns:scx="http://www.siemens.com/schema/csta"><scx:extendedServicesPermitted/></private></privateData></extensions></ServiceInitiatedEvent>')
    a.append(b'\x00\x00\x04C9999<?xml version="1.0" encoding="UTF-8"?><OriginatedEvent xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><monitorCrossRefID>1169730059</monitorCrossRefID><originatedConnection><callID>FF000100000000002D65C85C1C750000</callID><deviceID>302118840100</deviceID></originatedConnection><callingDevice><deviceIdentifier>302118840100</deviceIdentifier></callingDevice><calledDevice><deviceIdentifier>N&lt;302118840101&gt;;displayNumber=302118840101;noa=nk</deviceIdentifier></calledDevice><localConnectionInfo>connected</localConnectionInfo><cause>newCall</cause><servicesPermitted><callControlServices><clearConnection>true</clearConnection></callControlServices><callAssociatedServices/><mediaAttachementServices/><routeingServices/><voiceServices/></servicesPermitted><mediaCallCharacteristics><mediaClass><voice>true</voice><image>false</image><im>false</im></mediaClass></mediaCallCharacteristics><extensions><privateData><private xmlns:scx="http://www.siemens.com/schema/csta"><scx:extendedServicesPermitted/></private></privateData></extensions></OriginatedEvent>')
    a.append(b'\x00\x00\x04A0002<?xml version="1.0" encoding="UTF-8"?><MonitorStop xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><monitorCrossRefID>1193240031</monitorCrossRefID><extensions><privateData><private xmlns:scx="http://www.siemens.com/schema/csta"><scx:staticOndDN>17133013</scx:staticOndDN></private></privateData></extensions></MonitorStop>')
    a.append(b'\x00\x00\xb4A0002<?xml version="1.0" encoding="UTF-8"?><StartApplicationSessionPosResponse xmlns:aps="http://www.ecma-international.org/standards/ecma-354/appl_session"><sessionID>009968951</sessionID><actualProtocolVersion>http://www.ecma-international.org/standards/ecma-323/csta/ed4</actualProtocolVersion><actualSessionDuration>600</actualSessionDuration><extensions><actualHBT>0</actualHBT></extensions></StartApplicationSessionPosResponse>')
    b.append('''<?xml version="1.0" encoding="utf-8"?>
<MonitorStart>
   <monitorObject>
      <deviceObject>{user}</deviceObject>
   </monitorObject>
   <monitorType>device</monitorType>
   <extensions>
      <privateData>
         <private xmlns:scx="http://www.siemens.com/schema/csta">
            <scx:staticOndDN>17133013</scx:staticOndDN>
         </private>
      </privateData>
   </extensions>
</MonitorStart>''')
    a.append(b'\x00\x00\x04A0002<?xml version="1.0" encoding="UTF-8"?><SystemRegisterResponse xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><sysStatRegisterID>27ss</sysStatRegisterID></SystemRegisterResponse>')
    a.append(b'\x00\x00\x04A0002<?xml version="1.0" encoding="UTF-8"?><MonitorStartResponse xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><monitorCrossRefID>1136370025</monitorCrossRefID></MonitorStartResponse>')
    b.append('''<?xml version="1.0" encoding="utf-8"?>
<StartApplicationSession>
   <applicationInfo>
      <applicationID>pythontsm</applicationID>
   </applicationInfo>
   <requestedProtocolVersions>
      <protocolVersion>http://www.ecma-international.org/standards/ecma-323/csta/ed4</protocolVersion>
   </requestedProtocolVersions>
   <requestedSessionDuration>600</requestedSessionDuration>
</StartApplicationSession>''')
    b.append('''<?xml version="1.0" encoding="UTF-8"?>
<SystemStatus
  xmlns="http://www.ecma.ch/standards/ecma-323/csta/ed2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="
      http://www.ecma.ch/standards/ecma-323/csta/ed2  file://localhost/X:/ips_bln/long_csta/ecma/system-status.xsd
  ">
  <systemStatus>normal</systemStatus>
</SystemStatus>''')
    b.append('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><ns3:SystemStatus xmlns:ns2="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns3="http://www.ecma-international.org/standards/ecma-323/csta/ed4"/>''')
    b.append('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><ns3:MonitorStart xmlns:ns2="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns3="http://www.ecma-international.org/standards/ecma-323/csta/ed4"><ns3:monitorObject><ns3:deviceObject typeOfNumber="dialingNumber">3021033</ns3:deviceObject></ns3:monitorObject></ns3:MonitorStart>''')
    b.append('<?xml version="1.0" encoding="utf-8"?><DeflectCall><callToBeDiverted><deviceID>SUB_C</deviceID><callID>FF000100000000006BB1234C31000000</callID></callToBeDiverted><newDestination>SUB_D</newDestination></DeflectCall>')
    b.append('''<?xml version='1.0' encoding='utf-8'?><CallInformationEvent xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4" xmlns:scx="http://www.siemens.com/schema/csta"><monitorCrossRefID>1166743342</monitorCrossRefID><connection><callID>FF00010000000000E2E00E6416060000</callID><deviceID>3021061290000</deviceID></connection><device><deviceIdentifier>N&lt;3021061290000&gt;;noa=nk</deviceIdentifier></device><correlatorData><string>75726E3A6E656E613A7569643A63616C6C69643A7535543341316E627635462E6F7376636932306E312E68386B2E7365633B75726E3A6E656E613A7569643A696E636964656E7469643A527A6E447039543643756E2E6F7376636932306E312E68386B2E736563</string></correlatorData><connectionInfo><mediaSessionInfo>voice</mediaSessionInfo></connectionInfo><callCharacteristics><acdCall>true</acdCall><priorityCall>true</priorityCall><highPriorityCall>true</highPriorityCall><sensitiveCall>true</sensitiveCall></callCharacteristics><extensions><privateData><private><scx:aliQueryTimeout><scx:aliDBInfo>10.2.31.5:9991</scx:aliDBInfo><scx:aliConfiguredTimeout>200</scx:aliConfiguredTimeout></scx:aliQueryTimeout></private></privateData></extensions></CallInformationEvent>''')
    b.append('''<?xml version="1.0" encoding="UTF-8"?>
<DeliveredEvent xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4">
   <monitorCrossRefID>1173673890</monitorCrossRefID>
   <connection>
      <callID>FF00010000000000EC6114647E570000</callID>
      <deviceID>3021061290002</deviceID>
   </connection>
   <alertingDevice>
      <deviceIdentifier>N&lt;3021061290002&gt;;noa=nk</deviceIdentifier>
   </alertingDevice>
   <callingDevice>
      <deviceIdentifier>N&lt;7868772298&gt;Line71001;displayNumber=7868772298;uid=FF00010000000000EC6114647E570000</deviceIdentifier>
   </callingDevice>
   <calledDevice>
      <deviceIdentifier>N&lt;3021061290002&gt;;noa=nk</deviceIdentifier>
   </calledDevice>
   <lastRedirectionDevice>
      <notRequired/>
   </lastRedirectionDevice>
   <localConnectionInfo>alerting</localConnectionInfo>
   <correlatorData>
      <string>
         7
         5
         7
         2
         6
         E
         3
         A6E656E613A7569643A63616C6C69643A42544F43696C6A7332344D2E6F7376636932306E312E68386B2E7365633B75726E3A6E656E613A7569643A696E636964656E7469643A746669477346763462525A2E6F7376636932306E312E68386B2E736563
      </string>
   </correlatorData>
   <cause>enteringDistribution</cause>
   <servicesPermitted>
      <callControlServices>
         <clearConnection>true</clearConnection>
         <deflectCall>true</deflectCall>
      </callControlServices>
      <callAssociatedServices/>
      <mediaAttachementServices/>
      <routeingServices/>
      <voiceServices/>
   </servicesPermitted>
   <networkCalledDevice>
      <deviceIdentifier>02911</deviceIdentifier>
   </networkCalledDevice>
   <associatedCallingDevice>
      <notKnown/>
   </associatedCallingDevice>
   <mediaCallCharacteristics>
      <mediaClass>
         <voice>true</voice>
         <image>false</image>
         <message>false</message>
      </mediaClass>
   </mediaCallCharacteristics>
   <callCharacteristics>
      <acdCall>true</acdCall>
      <priorityCall>true</priorityCall>
      <highPriorityCall>true</highPriorityCall>
      <sensitiveCall>true</sensitiveCall>
   </callCharacteristics>
   <extensions>
      <privateData>
         <private xmlns:scx="http://www.siemens.com/schema/csta">
            <scx:cdrTrunkSeizureDateTime>2023/03/17 14:49:48</scx:cdrTrunkSeizureDateTime>
            <scx:extendedServicesPermitted/>
         </private>
      </privateData>
   </extensions>
</DeliveredEvent>''')
    # for i in a:
    #     m = parseBytes(i)
    #     print(m["monitorCrossRefID"])
    #     if m["monitorCrossRefID"] is None:
    #         print(m)
    for j in b:
        m = buildMessage(j, {"user": "12313213"}, eventid=2222)
        if m["deviceID"] and m["callID"]:
            # print(m["deviceID"], m["callID"])
            # m["deviceID"] = "user.deviceID"
            # m["callID"] = "user.callID"
            # print(m["deviceID"], m["callID"])
            pass
        print(m)
        # print("`````", m["callID"])
        # print("=====", m.body.get_all("deviceIdentifier"))
    last = buildMessage(j, {"user": "12313213"}, eventid=2222)["deviceObject"]



