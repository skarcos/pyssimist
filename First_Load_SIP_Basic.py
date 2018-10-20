from client import TCPClient
from SipParser import parseBytes,buildMessage
from messages import message
from time import sleep
import util
from concurrent.futures import ThreadPoolExecutor

link={}
talkDuration=10
parameters=util.dict_2({"dest_ip":"10.2.28.54",
            "dest_port":5060,
            "transport":"tcp",
            "callId":util.randomCallID,
            "fromTag":util.randomTag,
            "source_ip":util.getLocalIP,
#            "source_port":5080,
            "viaBranch":util.randomBranch,
            "epid":lambda x=6: "SC"+util.randStr(x),
            "bodyLength":"0",
            "expires":"360"
            })

def Connect(user_range,baseLocalPort,localIP=util.getLocalIP()):
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
    #print(m)
    L.send(m.contents())
    inBytes=L.waitForData()
    inmessage=parseBytes(inBytes)
    #print(inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK","{}\n{}".format(user,inmessage)


def Unregister(user):
    parameters["expires"]="0"
    Register(user)

def flow(users):
    usera=next(users)
    userb=next(users)
    parameters["userA"]=usera
    parameters["userB"]=userb

    parameters["source_port"]=link[usera].port
    Invite=buildMessage(message["Invite_SDP_1"],parameters)
    #print(Invite)
    link[usera].send(Invite.contents())
    
    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="100 Trying",\
           "Sent:\n{}Received:\n{}".fomrat(Invite,inmessage)

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
    toTag=";tag="+util.randStr(8)
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
    NumberOfUsers=10
    calls=1
    secondsPer=3
    userPool=["302128810"+"%03d" % i for i in range(NumberOfUsers)]
    link=Connect(userPool,baseLocalPort=6280)
    for user in userPool:
        Register(user)
        sleep(0.1)

    test=util.Load(flow,
                   util.loop(userPool),
                   duration=60,
                   quantity=calls,
                   interval=secondsPer,
                   spawn="threads")
    
    for user in userPool:
        Unregister(user)
        sleep(0.1)

    # Close the connection
    #C.close()
    # If I don't though, the socket remains open, else it goes into TIME_WAIT for 3 minutes
