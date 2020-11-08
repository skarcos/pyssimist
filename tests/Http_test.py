from _http.HttpEndpoint import HttpEndpoint
from _http.HttpParser import buildMessage, parseBytes
from _http.messages import message
from common import client

# parameters = {"host": "www.in.gr", "path": "/"}
# Get = buildMessage(message["Get_1"], parameters)
# link = client.TCPClient("192.168.2.12", 0)
# link.connect("www.in.gr", 80)
# link.send(Get.contents())
# response = link.waitForData(50)
# print(parseBytes(response))

post = '''POST / HTTP/1.1
Host: 10.2.5.6:4465
Content-Type: application/lost+xml                                                                                              
Cache-Control: no-cache                                                                                                         
Accept: application/xml                                                                                                         
Content-Length: 423                                                                                                             
                                                                                                                                
<?xml version="1.0" encoding="UTF-8"?><findService xmlns="urn:ietf:params:xml:ns:lost1" recursive="false" serviceBoundary="value">
<location id="e5lpsz3aYh1mPYrRDJQ37pkdfFdfc3LH" profile="civic">                                                                
<civicAddress xmlns="urn:ietf:params:xml:ns:pidf:geopriv10:civicAddr">                                                          
<country>GR</country>                                                                                                           
<A1>AT</A1>                                                                                                                     
<A2>011</A2>                                                                                                                    
<A3>Athens</A3>                                                                                                                 
<RD>Irakleiou</RD></civicAddress>                                                                                               
</location><service>urn:service:sos</service></findService>                                                                     
'''
# Post = buildMessage(post, {})
# link = client.TCPClient("127.0.0.1", 2000)
# link.connect("127.0.0.1", 4445)
# link.send(Post.contents())
# response = link.waitForData(50)
# print(parseBytes(response))

A = HttpEndpoint("")
A.connect(("127.0.0.1", 0), ("127.0.0.1", 4445))
A.send_new(message_string=post)
print(A.waitForMessage("200"))