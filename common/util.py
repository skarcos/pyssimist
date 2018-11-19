"""\
Purpose: Utility functions and classes
Initial Version: Costas Skarakis 11/11/2018
"""
import random
import string
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from threading import Timer, Thread
from time import time

from common.tc_logging import logger


def nowHex():
    """ Current time in sec represented in hex - 4 digits """
    return '{:x}'.format(int(time()))


def randStr(digits):
    """ Returns a random string with this many digits"""
    return ''.join((random.choice(string.ascii_lowercase + string.digits) for n in range(digits)))


def randomCallID():
    return nowHex() + randStr(12)


def randomTag():
    return nowHex() + randStr(4)


def getLocalIP():
    # TODO
    return "10.2.31.5"


def randomBranch():
    return nowHex() + randStr(24)


def epid(*args):
    """ User args to get a unique epid """
    # if we always seed random generation with the same string, the next random number will be the same
    random.seed(''.join(args))
    return hex(random.getrandbits(32))[2:]


def loop(sequence):
    while True:
        for i in sequence:
            yield i


def serverThread(target, *args, **kwargs):
    """ Start a thread """
    ex = ThreadPoolExecutor()
    thread = ex.submit(target, *args, **kwargs)
    return thread


class dict_2(dict):
    """
    Override dictionary getitem, to call items that are callable
    """

    def __getitem__(self, item):
        value = dict.__getitem__(self, item)
        if callable(value):
            return value()
        else:
            return value


class Load(object):
    """
    Start a performance run
    """

    def __init__(self,
                 flow,
                 *flow_args,
                 interval=1.0,
                 quantity=1,
                 duration=0,
                 stopCondition=None):
        self.flow = flow
        self.args = flow_args
        self.interval = interval
        self.quantity = quantity
        self.duration = duration
        self.stopCondition = stopCondition
        self.startTime = time()
        self.active = []

    def start(self):
        """
        Every :interval seconds, start :quantity flows
        """
        for i in range(self.quantity):
            self.runNextFlow()
        if not self.stopCondition and (self.duration < 0 or time() - self.startTime < self.duration):
            Timer(self.interval, self.start).start()
        else:
            self.stop()

    def stop(self):
        """
        Set the stopCondition to stop so that no new execution will be scheduled.
        The running executions will not be interrupted
        """
        self.stopCondition = True

    def runNextFlow(self):
        c = LoadThread(target=self.flow, args=self.args)
        c.start()
        self.active.append(c)

    def monitor(self):
        while self.active or not self.stopCondition:
            for inst in (ins for ins in self.active if not ins.is_alive()):
                inst.join()
                self.active.remove(inst)


class LoadThread(Thread):
    """ I had to make a custom thread class to handle exceptions """
    def run(self):
        try:
            super().run()
        except:
            logger.exception("Exception in Thread")
