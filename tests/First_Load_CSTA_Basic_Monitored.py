import sys
sys.path.append("..")
from common.client import TCPClient
from sip.SipParser import parseBytes,buildMessage
from csta.CstaParser import parseBytes as parseBytes_csta
from csta.CstaParser import buildMessageFromFile
from sip.messages import message
from time import sleep
from socket import timeout
from common import util
import os

xmlpath=r".\CstaPool"
link={}
serverThreads=[]
talkDuration=10
parameters= util.dict_2({"dest_ip": "10.2.28.54",
                        "dest_ip_csta":"10.2.28.60",
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

def getxml(name):
    return os.path.join(xmlpath,name)

def ConnectSip(user_range, baseLocalPort, localIP=util.getLocalIP()):
    " Open the connections for the users "
    connection_pool={}
    localPort=baseLocalPort
    for user in user_range:
        C=TCPClient(localIP,localPort)
        C.connect(parameters["dest_ip"],parameters["dest_port"])
        connection_pool[user]=C
        localPort=localPort+1
    return connection_pool

def ConnectCsta(user_range, localIP=util.getLocalIP()):
    " Open the connections for the users "
    connection_pool={}
    # We set 0 port to connect to any available port
    for user in user_range:
        C=TCPClient(localIP,0)
        C.connect(parameters["dest_ip_csta"],1040)

        inBytes=C.waitForData()
        req=parseBytes_csta(inBytes)

        resp=buildMessageFromFile(getxml("SystemStatusResponse.xml"),parameters,eventid=req.eventid)
        C.send(resp.contents())

        reg=buildMessageFromFile(getxml("SystemRegister.xml"),parameters,eventid=0)
        C.send(reg.contents())

        inBytes=C.waitForData()
        reg_resp=parseBytes_csta(inBytes)
        
        connection_pool[user]=C
    return connection_pool

def Register(user):
    parameters["user"]=user
    L=link[user]
    parameters["source_port"]=L.port
    m=buildMessage(message["Register_1"],parameters)
    #print(m)
    L.send(m.contents())
    inBytes=L.waitForData()
    inmessage=parseBytes(inBytes)
    #print(inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK","{}\n{}".format(user,inmessage)

def MonitorStart(user):
    parameters["user"]=user
    L=linkCsta[user]
    parameters["source_port"]=L.port
    m=buildMessageFromFile(getxml("MonitorStart.xml"),parameters,eventid=1)
    L.send(m.contents())
    inBytes=L.waitForData()
    inmessage=parseBytes_csta(inBytes)
    assert inmessage.event=="MonitorStartResponse", "Sent:{}  Received:{}".format(m.event,str(inmessage))

def WaitForCstaEvents(user,assertLeg=None):
    "Waits for CSTA messages until the CSTA link is not valid"
    
    if assertLeg in ("originator","initiator","A","Aside","caller"):
        assertMessageQueue=["ServiceInitiatedEvent","OriginatedEvent","DeliveredEvent","EstablishedEvent","ConnectionClearedEvent"]
    elif assertLeg in ("destination","target","B","Bside","callee"):
        assertMessageQueue=["DeliveredEvent","EstablishedEvent","ConnectionClearedEvent"]
    else:
        assertMessageQueue=[]
        
    L=linkCsta[user]
    while L:
        try:
            inBytes=L.waitForCstaData()
            inmessage=parseBytes_csta(inBytes)
            if assertMessageQueue:
                expectedEvent=assertMessageQueue.pop(0)
                assert inmessage.event==expectedEvent,\
                       "User {} expected {} but got {}".format(user,expectedEvent,inmessage.event)
            #print("User:{} received {}".format(user,inmessage))
        except timeout:
            pass
        finally:
            L=linkCsta[user]    
    
def Unregister(user):
    parameters["expires"]="0"
    Register(user)

def flow(users):
    usera=next(users)
    userb=next(users)
    parameters["userA"]=usera
    parameters["userB"]=userb
    serverThreads.append(util.serverThread(WaitForCstaEvents, usera, assertLeg="A"))
    serverThreads.append(util.serverThread(WaitForCstaEvents, userb, assertLeg="B"))
    parameters["source_port"]=link[usera].port
    Invite=buildMessage(message["Invite_SDP_1"],parameters)
    #print(Invite)
    link[usera].send(Invite.contents())
    
    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="100 Trying",\
           "Sent:\n{}Received:\n{}".fomrat(Invite,inmessage)

#    inBytes=linkCsta[usera].waitForData()
#    cstaevent=parseBytes_csta(inBytes)
#    assert cstaevent.event=="ServiceInitiated", "Expected:{}  Received:{}".format("ServiceInitiated",str(cstaevent))

    inBytes=link[userb].waitForData()
    inmessageb=parseBytes(inBytes)
    #print("IN:",inmessageb)
    assert inmessageb.type=="Request" and inmessageb.method=="INVITE",\
           "A side sent:\n{}and got Trying, but B side received:\n{}".format(Invite,inmessage)
    
    parameters["source_port"]=link[userb].port
    m=buildMessage(message["Trying_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      m[h]=inmessageb[h]
    #print(m)
    link[userb].send(m.contents())

    parameters["source_port"]=link[userb].port
    Ringing=buildMessage(message["Ringing_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      Ringing[h]=inmessageb[h]
    toTag=";tag=" + util.randStr(8)
    Ringing["To"]=Ringing["To"]+toTag
    #print(Ringing)
    link[userb].send(Ringing.contents())
    
    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="180 Ringing",\
           "B side sent:\n{}but A side received:\n{}".format(Ringing,inmessage)



    parameters["source_port"]=link[userb].port
    m=buildMessage(message["200_OK_SDP_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      m[h]=Ringing[h]
    m["To"]=m["To"]+toTag
    #print(m)
    link[userb].send(m.contents())

    inBytes=link[userb].waitForData()
    ack=parseBytes(inBytes)
    #print("IN:",ack)
    assert ack.type=="Request" and ack.method=="ACK",\
           "Sent:\n{}Received:\n{}".format(m,ack)

    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK",\
           "B side got:\n{}but A side received:\n{}".format(ack,inmessage)

    parameters["source_port"]=link[usera].port
    m=buildMessage(message["Ack_1"],parameters)
    for h in ("To","From","Call-ID"):
      m[h]=inmessage[h]
    #print(m)
    link[usera].send(m.contents())


    sleep(talkDuration)

    parameters["source_port"]=link[usera].port
    m=buildMessage(message["Bye_1"],parameters)
    for h in ("To", "From","Call-ID"):
      m[h]=inmessage[h]
    #print(m)
    link[usera].send(m.contents())

    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK",\
           "Sent:\n{}Received:\n{}".format(m,inmessage)

    inBytes=link[userb].waitForData()
    Bye=parseBytes(inBytes)
    #print("IN:",Bye)
    assert Bye.type=="Request" and Bye.method=="BYE",\
           "A side sent:\n{}B side received:\n{}".format(m,inmessage)

    parameters["source_port"]=link[userb].port
    m=buildMessage(message["200_OK_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      m[h]=Bye[h]
    #print(m)
    link[userb].send(m.contents())   

if __name__=="__main__":
    NumberOfUsers=4
    calls=1
    secondsPer=1
    userPool=["302118840"+"%03d" % i for i in range(NumberOfUsers)]
    cstaPool=["302118840"+"%03d" % i for i in range(NumberOfUsers)]
    link=ConnectSip(userPool,baseLocalPort=6280)
    try:
        linkCsta=ConnectCsta(cstaPool)
    except:
        print("Cannot connect to port 1040. Is the firewall is blocking the connection?")
        raise
    try:
        for user in userPool:
            Register(user)
            MonitorStart(user)
            sleep(0.1)

        test= util.Load(flow,
                        util.loop(userPool),
                        duration=0,
                        quantity=calls,
                        interval=secondsPer,
                        spawn="threads")
        
    finally:
        for user in userPool:
            Unregister(user)
            linkCsta[user]=None
            sleep(0.1)
        print("Unregister done")
        # join all threads
        for thread in serverThreads:
            thread.result()
    # Close the connection
    #C.close()
    # If I don't though, the socket remains open, else it goes into TIME_WAIT for 3 minutes
