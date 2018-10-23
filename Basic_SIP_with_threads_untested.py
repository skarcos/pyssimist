from client import TCPClient
from SipParser import parseBytes,buildMessage
from messages import message
from time import sleep
from socket import timeout
import util
from concurrent.futures import ThreadPoolExecutor
from threading import local
import os

xmlpath=r".\CstaPool"
link={}
agentThreads=[]
busyCallers=[]
talkDuration=10
# Create thread local data
data=local()
data.parameters=util.dict_2({"dest_ip_orig":"10.5.42.44",
                             "dest_ip_psap":"10.9.65.45",
                             "dest_port":5060,
                             "transport":"tcp",
                             "callId":util.randomCallID,
                             "fromTag":util.randomTag,
                             "source_ip":"10.2.31.5",
                 #            "source_port":5080,
                             "viaBranch":util.randomBranch,
                             "epid":lambda x=6: "SC"+util.randStr(x),
                             "bodyLength":"0",
                             "expires":"1800"
                             })

def getxml(name):
    return os.path.join(xmlpath,name)

def ConnectSip(user_range,baseLocalPort,localIP=util.getLocalIP()):
    " Open the connections for the users "
    connection_pool={}
    localPort=baseLocalPort
    for user in user_range:
        C=TCPClient(localIP,localPort)
        C.connect(data.parameters["dest_ip"],data.parameters["dest_port"])
        connection_pool[user]=C
        localPort=localPort+1
    return connection_pool

def Register(user):
    data.parameters["user"]=user
    L=link[user]
    data.parameters["source_port"]=L.port
    m=buildMessage(message["Register_1"],data.parameters)
    #print(m)
    L.send(m.contents())
    inBytes=L.waitForData()
    inmessage=parseBytes(inBytes)
    #print(inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK","{}\n{}".format(user,inmessage)

    
def WaitForCall(user):
    " Start an agent. Wait for INVITE messages"
    L=link[user]
    expectedMessage="INVITE"
    while L:
    # Will stop when we set the link of the user to None
        try:
            inBytes=L.waitForData()
            inmessage=parseBytes(inBytes)
            assert inmessage.type==expectedEvent,\
                    "User {} expected {} but got {}".format(user,expectedEvent,inmessage.event)
            #print("User:{} received {}".format(user,inmessage))
        except timeout:
            pass
        finally:
            L=link[user]    
    try:
        data.parameters["userB"]=user
        data.parameters["source_port"]=link[user].port
        m=buildMessage(message["Trying_1"],data.parameters)
        for h in ("To", "From", "CSeq","Via","Call-ID"):
          m[h]=inmessageb[h]
        #print(m)
        link[user].send(m.contents())

        data.parameters["source_port"]=link[user].port
        Ringing=buildMessage(message["Ringing_1"],data.parameters)
        for h in ("To", "From", "CSeq","Via","Call-ID"):
          Ringing[h]=inmessageb[h]
        toTag=";tag="+util.randStr(8)
        Ringing["To"]=Ringing["To"]+toTag
        #print(Ringing)
        link[user].send(Ringing.contents())

        data.parameters["source_port"]=link[user].port
        m=buildMessage(message["200_OK_SDP_1"],data.parameters)
        for h in ("To", "From", "CSeq","Via","Call-ID"):
          m[h]=Ringing[h]
        m["To"]=m["To"]+toTag
        #print(m)
        link[user].send(m.contents())

        inBytes=link[user].waitForData()
        ack=parseBytes(inBytes)
        #print("IN:",ack)
        assert ack.type=="Request" and ack.method=="ACK",\
               "Sent:\n{}Received:\n{}".format(m,ack)
        
        inBytes=link[user].waitForData()
        Bye=parseBytes(inBytes)
        #print("IN:",Bye)
        assert Bye.type=="Request" and Bye.method=="BYE",\
               "A side sent:\n{}B side received:\n{}".format(m,inmessage)

        data.parameters["source_port"]=link[user].port
        m=buildMessage(message["200_OK_1"],data.parameters)
        for h in ("To", "From", "CSeq","Via","Call-ID"):
          m[h]=Bye[h]
        #print(m)
        link[user].send(m.contents())   

        
    finally:
        # When call is done wait for next call
        AgentState(user)
        
def Unregister(user):
    data.parameters["expires"]="0"
    Register(user)

def flow(users,pilot):
    usera=next(users)
    data.parameters["userA"]=usera
    data.parameters["userB"]=pilot
    data.parameters["source_port"]=link[usera].port
    Invite=buildMessage(message["Invite_SDP_1"],data.parameters)
    #print(Invite)
    link[usera].send(Invite.contents())
    
    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="100 Trying",\
           "Sent:\n{}Received:\n{}".format(Invite,inmessage)

    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="180 Ringing",\
           "B side sent:\n{}but A side received:\n{}".format(Ringing,inmessage)


    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK",\
           "B side got:\n{}but A side received:\n{}".format(ack,inmessage)

    data.parameters["source_port"]=link[usera].port
    m=buildMessage(message["Ack_1"],data.parameters)
    for h in ("To","From","Call-ID"):
      m[h]=inmessage[h]
    #print(m)
    link[usera].send(m.contents())


    sleep(talkDuration)

    data.parameters["source_port"]=link[usera].port
    m=buildMessage(message["Bye_1"],data.parameters)
    for h in ("To", "From","Call-ID"):
      m[h]=inmessage[h]
    #print(m)
    link[usera].send(m.contents())

    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK",\
           "Sent:\n{}Received:\n{}".format(m,inmessage)


if __name__=="__main__":
    NumberOfCallers=10
    NumberOfAgents=10
    calls=1
    secondsPer=1
    pilot="77911"
    callers=["302102310"+"%03d" % i for i in range(NumberOfCallers)]
    agents=["302118840"+"%03d" % i for i in range(NumberOfAgents)]
    link=ConnectSip(callers,baseLocalPort=6280)
    link.update(ConnectSip(agents,baseLocalPort=6280+NumberOfCallers))
    try:
        for user in callers+agents:
            Register(user)
            sleep(0.1)

        for agent in agents:
            agentThreads.append(util.serverThread(WaitForCall,user))
            sleep(0.1)

        test=util.Load(flow,
                       util.loop(callers),
                       duration=0,
                       quantity=calls,
                       interval=secondsPer)
        
    finally:
        for user in userPool:
            Unregister(user)
            link[user]=None
            sleep(0.1)
        print("Unregister done")
        # join all threads
        for thread in agentThreads:
            thread.result()
    # Close the connection
    #C.close()
    # If I don't though, the socket remains open, else it goes into TIME_WAIT for 3 minutes
