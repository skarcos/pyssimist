from time import time
import random,string,traceback
from threading import Timer
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor, as_completed,wait

def nowHex():
    " Current time in sec represented in hex - 4 digits "
    return  '{:x}'.format(int(time()))

def randStr(digits):
    " Returns a random string with this many digits"
    return ''.join((random.choice(string.ascii_lowercase + string.digits) for n in range(digits)))

def randomCallID():
    return nowHex()+randStr(12)

def randomTag():
    return nowHex()+randStr(4)

def getLocalIP():
    #TODO
    return "10.2.31.5"

def randomBranch():
    return nowHex()+randStr(24)

def loop(sequence):
    while True:
        for i in sequence: 
            yield i

def serverThread(target,*args,**kwargs):
    ' Start a thread '
    ex=ThreadPoolExecutor()
    thread=ex.submit(target,*args,**kwargs)
    return thread

class dict_2(dict):
    '''
    Override dictionary getitem, to call items that are callable
    '''
    def __getitem__(self,item):
        value=dict.__getitem__(self,item)
        if callable(value):
            return value()
        else:
            return value

		
class Load(object):
    '''
    Start a performance run
    '''
    def __init__(self,
                 flow,
                 *flow_args,
                 interval=1.0,
                 quantity=1,
                 duration=0,
                 stopCondition=None,
                 spawn="threads"):
        self.flow=flow
        self.args=flow_args
        self.interval=interval
        self.quantity=quantity
        self.duration=duration
        self.stopCondition=stopCondition
        self.startTime=time()
        self.active=[]
        if spawn=="threads":
            self.executor=ThreadPoolExecutor
        elif spawn=="processes":
            self.executor=ProcessPoolExecutor
        else:
            raise Exception("Valid spawn argument values: threads, processes")
        self.start()
        self.monitor()

    def start(self):
        '''
        Every :interval seconds, start :quantity flows
        '''
        for i in range(self.quantity):
            self.runNextFlow()
        if self.duration == 0 or time()-self.startTime >= self.duration or self.stopCondition:
            self.stopCondition=True
            print("Execution ended")
            return
        t=Timer(self.interval,self.start)
        t.start()

    def runNextFlow(self):
        ex=self.executor()
        self.active.append(ex.submit(self.flow,*self.args))

    def monitor(self):
        while any(x.running() for x in self.active) or not self.stopCondition:
            for inst in as_completed(self.active):
                try:
                    inst.result()
                except:
                    traceback.print_exc()
