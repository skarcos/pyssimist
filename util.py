from time import time
import random,string
import threading as th

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

		
