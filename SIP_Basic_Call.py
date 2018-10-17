from client import TCPClient
from SipParser import parseBytes,buildMessage
from messages import message
from time import sleep
import util

usera="302108100001"
userb="302108100501"
talkDuration=10
parameters=util.dict_2({"dest_ip":"10.2.0.22",
            "dest_port":5060,
            "transport":"tcp",
            "callId":util.randomCallID,
            "fromTag":util.randomTag,
            "source_ip":util.getLocalIP,
            "source_port":5080,
            "viaBranch":util.randomBranch,
            "epid":lambda x=6: "SC"+util.randStr(x),
            "bodyLength":"0",
            "expires":"360"
            })

# Open the connections
C=TCPClient(parameters["source_ip"],parameters["source_port"])
C.connect(parameters["dest_ip"],parameters["dest_port"])

link={usera:C,userb:C}

def Register(user):
    parameters["user"]=user
    m=buildMessage(message["Register_1"],parameters)
    print(m)
    link[user].send(m.contents())
    inBytes=link[user].waitForData()
    inmessage=parseBytes(inBytes)
    print(inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK"


def Unregister(user):
    parameters["user"]=user
    parameters["expires"]="0"
    m=buildMessage(message["Register_1"],parameters)
    print(m)
    link[user].send(m.contents())
    inBytes=link[user].waitForData()
    inmessage=parseBytes(inBytes)
    print(inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK"


def flow():
    parameters["userA"]=usera
    parameters["userB"]=userb
    parameters["expires"]="0"

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

    parameters["callId"]=inmessage["Call-ID"]
    m=buildMessage(message["Trying_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      m[h]=inmessageb[h]
    print(m)
    link[userb].send(m.contents())

    Ringing=buildMessage(message["Ringing_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      Ringing[h]=inmessageb[h]
    toTag=";tag="+util.randStr(8)
    Ringing["To"]=Ringing["To"]+toTag
    print(Ringing)
    link[userb].send(Ringing.contents())
    
    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="180 Ringing"

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

    m=buildMessage(message["Ack_1"],parameters)
    for h in ("To","From","Call-ID"):
      m[h]=inmessage[h]
    print(m)
    link[usera].send(m.contents())


    sleep(talkDuration)

    m=buildMessage(message["Bye_1"],parameters)
    for h in ("To", "From","Call-ID"):
      m[h]=inmessage[h]
    print(m)
    link[usera].send(m.contents())

    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK"

    inBytes=link[usera].waitForData()
    Bye=parseBytes(inBytes)
    print("IN:",Bye)
    assert Bye.type=="Request" and Bye.method=="BYE"

    m=buildMessage(message["200_OK_1"],parameters)
    for h in ("To", "From", "CSeq","Via","Call-ID"):
      m[h]=Bye[h]
    print(m)
    link[userb].send(m.contents())   


if __name__=="__main__":
    Register(usera)
    Register(userb)
    try:
        flow()
    except:
        Unregister(usera)
        Unregister(userb)
        raise

    # Close the connection
    #C.close()
    # If I don't though, the socket remains open, else it goes into TIME_WAIT for 3 minutes
