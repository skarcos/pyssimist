tc_message = {"GetAgentStateResponse": '''<?xml version="1.0" encoding="UTF-8"?>
<GetAgentStateResponse xmlns="http://www.ecma-international.org/standards/ecma-323/csta/ed4">
<agentStateList>
<agentStateEntry>
<agentID>{agentID}</agentID>
<loggedOnState>true</loggedOnState>
<agentInfo>
<agentInfoItem>
<agentState>agentReady</agentState>
</agentInfoItem>
</agentInfo>
</agentStateEntry>
</agentStateList>
</GetAgentStateResponse>''',
              "ClearConnection": '''<?xml version="1.0" encoding="UTF-8"?>
<ClearConnection
  xmlns="http://www.ecma.ch/standards/ecma-323/csta/ed2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="
      http://www.ecma.ch/standards/ecma-323/csta/ed2  file://localhost/X:/ips_bln/long_csta/ecma/clear-connection.xsd
  ">
  <connectionToBeCleared>
    <deviceID>{deviceID}</deviceID>
    <callID>{callID}</callID>
  </connectionToBeCleared>
</ClearConnection>
'''}