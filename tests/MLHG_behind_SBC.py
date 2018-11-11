import sys
sys.path.append("..")
from common.client import TCPClient
from sip.SipParser import parseBytes,buildMessage
from sip.messages import message
from time import sleep
from socket import timeout
import traceback
from common import util
from threading import local
from copy import copy

link={}
agentThreads=[]
busyCallers=[]
# Create thread local data
data=local()
parameters= util.dict_2({"dest_ip_orig": "10.5.42.44",
                             "dest_ip_psap":"10.9.65.45",
                             "dest_port":5060,
                             "transport":"tcp",
                             "callId": util.randomCallID,
                             "fromTag": util.randomTag,
                             "source_ip":"10.2.31.5",
                         #            "source_port":5080,
                             "viaBranch": util.randomBranch,
                             "epid":lambda x=6: "SC" + util.randStr(x),
                             "bodyLength":"0",
                             "expires":"360",
                             "talkDuration":10
                         })


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

def handleDA(request,response,user,pwd=None):
    "Add DA to message and send again"
    # Usual case in lab, password same as username
    if not pwd: pwd=user
    if response.type=="Response" and response.status=="401 Unauthorized":
        request.addAuthorization(response["WWW-Authenticate"],user,pwd)
        link[user].send(request.contents())
        inBytes=link[user].waitForData()
        return parseBytes(inBytes)
    else:
        return response
    
def Register(user):
    parameters["user"]=user
    L=link[user]
    parameters["source_port"]=L.port
    parameters["source_ip"]=L.ip
    parameters["dest_ip"]=L.rip
    parameters["dest_port"]=L.rport
    parameters["epid"]= util.epid(user)
    m=buildMessage(message["Register_2"],parameters)
    #print(m)
    L.send(m.contents())
    inBytes=L.waitForData()
    try:
        inmessage=handleDA(m,parseBytes(inBytes),user)
        assert inmessage.type=="Response" and inmessage.status=="200 OK","{}\n{}".format(user,inmessage)
    except:
        traceback.print_exc()

def Unregister(user):
    parameters["expires"]="0"
    Register(user)
    
def WaitForCall(user,param):
    " Start an agent. Wait for INVITE messages"
    parameters=copy(param)
    parameters["number"]=0
    L=link[user]
    expectedMessage="INVITE"
    while L:
    # Will stop when we set the link of the user to None
        try:
            inBytes=L.waitForData()
            invite=parseBytes(inBytes)
            assert invite.type=="Request" and invite.method==expectedMessage,\
                    "User {} expected {} but got:\n{}".format(user,expectedMessage,invite)
            #print("User:{} received {}".format(user,inmessage))
            break
        except timeout:
            pass
        finally:
            L=link[user]    
    if not L:
        return
    try:
        parameters["userB"]=user
        parameters["source_port"]=link[user].port
        m=buildMessage(message["Trying_1"],parameters)
        for h in ("To", "From", "CSeq","Via","Call-ID"):
          m[h]=invite[h]
        #print(m)
        link[user].send(m.contents())
        
        Ringing=buildMessage(message["Ringing_1"],parameters)
        for h in ("To", "From", "CSeq","Via","Call-ID"):
            Ringing[h]=invite[h]
        for h in ("Allow","Allow-Events","X-Siemens-Call-Type"):
            if h in invite.headers:
                Ringing[h]=invite[h]
        toTag=";tag=" + util.randStr(8)
        Ringing["To"]=Ringing["To"]+toTag
        #print(Ringing)
        link[user].send(Ringing.contents())

        sleep(0.5)

        m=buildMessage(message["200_OK_SDP_1"],parameters)
        # Preserve Content-Length
        bkp=m["Content-Length"]
        for h in Ringing.headers:#("To", "From", "CSeq","Via","Call-ID","Contact"):
            m[h]=Ringing[h]
        m["Content-Length"]=bkp
        link[user].send(m.contents())

        inBytes=link[user].waitForData()
        ack=parseBytes(inBytes)
        #print("IN:",ack)
        assert ack.type=="Request" and ack.method=="ACK",\
               "Sent:\n{}Received:\n{}".format(m,ack)

        nobye=True
        acceptable=("BYE","UPDATE")
        while nobye:
            inBytes=link[user].waitForData(2*parameters["talkDuration"])
            inmessage=parseBytes(inBytes)
            nobye=not (inmessage.type=="Request" and inmessage.method=="BYE")
            assert inmessage.type=="Request" and inmessage.method in acceptable,\
                   "Expected one of {} but received :\n{}".format(str(acceptable),inmessage)
            m=buildMessage(message["200_OK_1"],parameters)
            for h in ("To", "From", "CSeq","Via","Call-ID"):
              m[h]=inmessage[h]
            #print(m)
            link[user].send(m.contents())

    except:
        traceback.print_exc()
    finally:
        # When call is done wait for next call
        del parameters
        WaitForCall(user,param)
        


def flow(users,pilot,param):
    parameters=copy(param)
    usera=next(users)
    parameters["userA"]=usera
    parameters["userB"]=pilot
    parameters["source_port"]=link[usera].port

    Invite=buildMessage(message["Invite_SDP_1"],parameters)
    #print(Invite)
    link[usera].send(Invite.contents())
    
    inBytes=link[usera].waitForData()
    inmessage=handleDA(Invite,parseBytes(inBytes),user)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="100 Trying",\
           "Sent:\n{}Received:\n{}".format(Invite,inmessage)

    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="180 Ringing",\
           "A side received Trying and then :\n{}".format(inmessage)


    inBytes=link[usera].waitForData()
    inmessage=parseBytes(inBytes)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK",\
           "A side received Ringing and then:\n{}".format(inmessage)

    m=buildMessage(message["Ack_1"],parameters)
    for h in ("To","From","Call-ID"):
      m[h]=inmessage[h]
    #print(m)
    link[usera].send(m.contents())


    sleep(parameters["talkDuration"])
    
    m=buildMessage(message["Bye_1"],parameters)
    for h in ("To", "From","Call-ID"):
      m[h]=inmessage[h]
    #print(m)
    link[usera].send(m.contents())

    inBytes=link[usera].waitForData()
    inmessage=handleDA(m,parseBytes(inBytes),user)
    #print("IN:",inmessage)
    assert inmessage.type=="Response" and inmessage.status=="200 OK",\
           "Sent:\n{}Received:\n{}".format(m,inmessage)


if __name__=="__main__":
    NumberOfCallers=1
    NumberOfAgents=1
    calls=1
    secondsPer=1
    pilot="77911"
    callers=["302102310"+"%03d" % (30+i) for i in range(NumberOfCallers)]
    agents=["302106960"+"%03d" % (120+i) for i in range(NumberOfAgents)]
    #callers=["302128810"+"%03d" % i for i in range(NumberOfCallers)]    
    #agents=["302128820"+"%03d" % i for i in range(NumberOfAgents)]
    
    parameters["dest_ip"]=parameters["dest_ip_orig"]
    link=ConnectSip(callers,baseLocalPort=6280)

    parameters["dest_ip"]=parameters["dest_ip_psap"]
    link.update(ConnectSip(agents,baseLocalPort=6280+NumberOfCallers))

    try:
        for user in callers+agents:
            Register(user)
            sleep(0.1)

        for agent in agents:
            agentThreads.append(util.serverThread(WaitForCall, agent, parameters))
            sleep(0.1)

        test= util.Load(flow,
                        util.loop(callers),
                        pilot,
                        parameters,
                        duration=0,
                        quantity=calls,
                        interval=secondsPer)
        
    finally:
        for user in callers+agents:
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
