import sys
from os import path
sys.path.append(path.join("..", ".."))
from common.client import TCPClient
from sip.SipParser import parseBytes,buildMessage
from sip.messages import message
from time import sleep
from common import util

usera="302108100001"
userb="302108100501"
link={}
talkDuration=10
parameters= util.dict_2({"dest_ip": "10.2.0.22",
            "dest_port":5060,
            "transport":"tcp",
            "callId": util.randomCallID,
            "fromTag": util.randomTag,
            "source_ip": util.getLocalIP,
                         #            "source_port":5080,
            "viaBranch": util.randomBranch,
            "epid":lambda x=6: "SC" + util.randStr(x),
            "bodyLength":"0",
            "expires":"360"
                         })

def Connect(user_range, baseLocalPort, localIP=util.getLocalIP()):
    " Open the connections for the users "
    connection_pool={}
    localPort=baseLocalPort
    for user in user_range:        
        C=TCPClient(localIP,localPort)
        C.connect(parameters["dest_ip"],parameters["dest_port"])
        connection_pool[user]=C
        localPort=localPort+1
    return connection_pool

def Register(user):
    parameters["user"]=user
    L=link[user]
    parameters["source_port"]=L.port
    m=buildMessage(message["Register_1"],parameters)
    print(m)
    L.send(m.contents())
    inBytes=L.waitForData()
    inmessage=parseBytes(inBytes)
    print(inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK"


def Unregister(user):
    parameters["expires"]="0"
    Register(user)

def flow(usera, userb):
    parameters["userA"]=usera
    parameters["userB"]=userb

    parameters["source_port"]=link[usera].port
    Invite=buildMessage(message["Invite_SDP_1"],parameters)
    print(Invite)
    link[usera].send(Invite.contents())
    
    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="100 Trying"

    inBytes=link[userb].waitForData()
    inmessageb=parseBytes(inBytes)
    print("IN:",inmessageb)
    assert inmessageb.type=="Request" and inmessageb.method=="INVITE"

    parameters["source_port"]=link[userb].port
    parameters["callId"]=inmessage["Call-ID"]
    m=buildMessage(message["Trying_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      m[h]=inmessageb[h]
    print(m)
    link[userb].send(m.contents())

    parameters["source_port"]=link[userb].port
    Ringing=buildMessage(message["Ringing_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      Ringing[h]=inmessageb[h]
    toTag=";tag=" + util.randStr(8)
    Ringing["To"]=Ringing["To"]+toTag
    print(Ringing)
    link[userb].send(Ringing.contents())
    
    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="180 Ringing"

    parameters["source_port"]=link[userb].port
    m=buildMessage(message["200_OK_SDP_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      m[h]=Ringing[h]
    m["To"]=m["To"]+toTag
    print(m)
    link[userb].send(m.contents())

    inBytes=link[userb].waitForData()
    inmessage=parseBytes(inBytes)
    print("IN:",inmessage)
    assert inmessage.type=="Request" and inmessage.method=="ACK"

    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK"

    parameters["source_port"]=link[usera].port
    m=buildMessage(message["Ack_1"],parameters)
    for h in ("To","From","Call-ID"):
      m[h]=inmessage[h]
    print(m)
    link[usera].send(m.contents())


    sleep(talkDuration)

    parameters["source_port"]=link[usera].port
    m=buildMessage(message["Bye_1"],parameters)
    for h in ("To", "From","Call-ID"):
      m[h]=inmessage[h]
    print(m)
    link[usera].send(m.contents())

    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK"

    inBytes=link[userb].waitForData()
    Bye=parseBytes(inBytes)
    print("IN:",Bye)
    assert Bye.type=="Request" and Bye.method=="BYE"

    parameters["source_port"]=link[userb].port
    m=buildMessage(message["200_OK_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      m[h]=Bye[h]
    print(m)
    link[userb].send(m.contents())   

if __name__=="__main__":
    link=Connect([usera,userb],baseLocalPort=5080)
    Register(usera)
    Register(userb)
    try:
        flow(usera,userb)
    finally:
        Unregister(usera)
        Unregister(userb)
        

    # Close the connection
    #C.close()
    # If I don't though, the socket remains open, else it goes into TIME_WAIT for 3 minutes
