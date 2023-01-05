"""\
Purpose: Utility functions and classes
Initial Version: Costas Skarakis 11/11/2018
"""
import random
import string
from concurrent.futures import ThreadPoolExecutor
from itertools import cycle
from threading import Timer, Thread
from time import time, sleep
import re
import io
import xml.etree.ElementTree as ET
import logging.handlers
from common.tc_logging import logger
import traceback


def nowHex():
    """ Current time in sec represented in hex - 4 digits """
    return '{:x}'.format(int(time()))


def randStr(digits):
    """ Returns a random string with this many digits"""
    return ''.join((random.choice(string.ascii_lowercase + string.digits) for n in range(digits)))


def randomCallID():
    return nowHex() + randStr(12)


def randomTag():
    """ TODO Implement RFC 3261 Section 19.3 Tags """
    return nowHex() + randStr(4)


def getLocalIP():
    # TODO
    return "10.4.253.10"


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


def pool(sequence, condition=bool):
    """
    Cyclically yields the next member of a sequence unless the specified condition is False

    :param sequence: input sequence, eg a list
    :param condition: a function to be run on the next member eg:
            lambda x: x.registered
    :return: yields the next eligible member
    """
    p = cycle(sequence)
    while True:
        c = next(p)
        if condition(c):
            yield c
        else:
            continue


def next_available_sip(sip_pool):
    """Find the next available sip endpoint from a pool of endpoints"""
    busy = True
    a = None
    while busy:
        a = next(sip_pool)
        busy = a.busy
    if type(a).__name__ == "SipEndpointView":
        a.busy = True
        a.update_text()
        a.update_arrow()
        a.colour("green")
    return a


def make_available_sip(*sip_endpoints):
    for sip_endpoint in sip_endpoints:
        sip_endpoint.busy = False
        if type(sip_endpoint).__name__ == "SipEndpointView":
            sip_endpoint.colour("yellow")


def serverThread(target, *args, **kwargs):
    """ Start a thread """
    ex = ThreadPoolExecutor()
    thread = ex.submit(target, *args, **kwargs)
    return thread


def wait_for_sip_data(sockfile):
    content_length = -1
    data = b""
    data += sockfile.readline()

    while True:
        line = sockfile.readline()
        data += line
        if not line.strip():
            break
        try:
            header, value = [x.strip() for x in line.split(b":", 1)]
        except ValueError:
            print("Incorrect header line:", repr(line))
            print("Message up to that:", data)
            continue
        if header == b"Content-Length" or header == b"content-length":
            content_length = int(value)

    if not data.strip():
        raise EOFError

    body = ""
    if content_length > 0:
        body = sockfile.read(content_length)
        if len(body) < content_length:
            raise IncompleteData
        else:
            data += body

    if content_length == -1:
        raise IncompleteData("No content length in message: " + repr(data))
    return data


class NoData(Exception):
    pass


class IncompleteData(Exception):
    pass


class XmlBody:
    """
    Very simple representation of an xml document

    Get tags as elements with ["tag_name"] or get_tag("tag_name") eg:
        reason_element = xml_body_1["reason"]
        reason_element = xml_body_1.get_tag("reason")
    Set tag text with assignment to tag element eg:
        xml_body_1["reason"] = "Global failure"
    or assign to the element text attribute:
        xml_body_1["reason"].text = "Global failure"
    Set tag attribute with element.set(attribute, value) eg:
        xml_body_1["internalError"].set("message","foo"))
        xml_body_1.get("internalError").set("message","foo"))

    In case the same tag is appearing multiple times get a list with get_all.
    Then you can modify each appearance by iterating on the elements. eg:
        for element in xml_body_1.get_all("tag_name"):
            if element.get("message") == "foo":
                element.text = "bar"

    The above will change this xml:
    <?xml version="1.0"?>
    <tags xmlns="http://people.example.com">
        <tag_name message="not foo">Text1</tag_name>
        <tag_name message="foo">Text2</tag_name>
    </tags>

    To this xml:
    <?xml version="1.0"?>
    <tags xmlns="http://people.example.com">
        <tag_name message="not foo">Text1</tag_name>
        <tag_name message="foo">bar</tag_name>
    </tags>

    Some of these operations may fail in some cases of XML documents with multiple namespaces (not all cases)
    """

    def __init__(self, xml_content, default_encoding="UTF-8",
                 default_namespace="http://www.ecma-international.org/standards/ecma-323/csta/ed4"):
        self.encoding = default_encoding
        if isinstance(xml_content, bytes):
            xml_encoding = re.search(b"encoding=[\'\"](.*)[\'\"] ?\?>", xml_content)
            if xml_encoding:
                self.encoding = xml_encoding.group(1).decode(encoding=default_encoding)
            self.ns_map = self.parse_map(io.StringIO(xml_content.decode(self.encoding)))
        else:
            xml_encoding = re.search("encoding=[\'\"](.*)[\'\"] ?\?>", xml_content)
            if xml_encoding:
                self.encoding = xml_encoding.group(1)
            self.ns_map = self.parse_map(io.StringIO(xml_content))
        try:
            self.body = xml_content.strip()
        except:
            print(xml_content)
            raise
        try:
            root = ET.fromstring(self.body)
        except:
            print(self.body)
            raise
        self.tree = ET.ElementTree(root)
        self.root = self.tree.getroot()
        ns = re.search("^{(.*)}", root.tag)
        if ns:
            self.namespace = ns.group(1)
        else:
            print("Warning: No namespace defined in message", root.tag)
            self.namespace = default_namespace
        #        self.ns_map = dict(re.findall("xmlns:(?P<name>.+) ?= ?[\'\"]?(?P<ns>[^\'\"]+)[\'\"]?[\s> ]",xml_content))
        ET.register_namespace("", self.namespace)
        self.event = self.root.tag.replace("{" + self.namespace + "}", '')

    def parse_map(self, file):
        """
        http://effbot.org/zone/element-namespaces.htm#parsing-with-prefixes

        :return: root tag of xml
        """
        events = "start", "start-ns", "end-ns"

        root = None
        ns_map = []
        count = 0
        for event, elem in ET.iterparse(file, events):
            if event == "start-ns":
                ns_map.append(("ns%d" % count, elem[1]))
                count += 1
        return dict(ns_map)

    def __getitem__(self, key, position="root"):
        """
         Find a tag using the default namespace
        :param key: The requested tag
        :param position: The element to look below
        :return: The first tag in any namespace
        """
        if position == "root":
            position = self.root
        clause = "{" + self.namespace + "}" + key
        if position.tag == clause:
            return position
        else:
            element = position.find(clause)
            if not element:
                for name in self.ns_map:
                    element = position.find(name + ":" + key, self.ns_map)
                    if element: break
            return element

    def get_tag(self, tag, parent="root"):
        """
        Find a tag using tag name, ignoring namespaces
        :param tag: The name of the tag
        :return:
        """
        if parent == "root":
            parent = self.root
        ch = None
        if parent.tag.endswith("}" + tag):
            return parent
        else:
            for child in parent:
                ch = self.get_tag(tag, parent=child)
                if ch is not None:
                    return ch

    def get_all(self, tag, position="root"):
        """
         Find all tags with this name in all namespaces
        :param key: The requested tag name
        :param position: The element to look below
        :return: A list of all elements with specified tag
        """
        if position == "root":
            position = self.root
        elements = []
        if position.tag.endswith("}" + tag):
            elements.append(position)
        else:
            for child in position:
                ch = self.get_tag(tag, parent=child)
                if ch is not None:
                    elements.append(ch)
        return elements

    def get_child(self, parent, tag):
        """
        Find a tags under given parent tag
        :param parent: A xlm tag element
        :param tag: The requested tag name
        :return: The first element found with the requested tag
        """
        return self.get_tag(tag, parent)

    def get_all_children(self, parent, tag):
        """

        :param parent:
        :param tag:
        :return:
        """
        return self.get_all(tag, position=parent)

    def __setitem__(self, key, value):
        element = self.tree.find("{" + self.namespace + "}" + key)
        element.text = value

    def __repr__(self):
        result = io.BytesIO()
        self.tree.write(result, xml_declaration=self.encoding, encoding=self.encoding)
        result.flush()
        return result.getvalue().decode(encoding=self.encoding)

    def __str__(self):
        return repr(self)


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
        st_logger = logging.getLogger('Statistics')
        handler = logging.handlers.RotatingFileHandler("Statistics.txt", mode="w", maxBytes=20000000, backupCount=5)
        st_logger.addHandler(handler)
        self.log = st_logger
        self.calls = {"Started": 0, "Finished": 0, "Passed": 0}
        self.loop = LoadThread(target=self._start)
        self.statistics()

    def start(self):
        self.loop.start()

    def _start(self):
        """
        Every :interval seconds, start :quantity flows
        """
        while not (self.stopCondition or not (self.duration < 0 or time() - self.startTime < self.duration)):
            t = time()
            for i in range(self.quantity):
                self.run_next_flow()
                sleep(max((0, self.interval-time()+t)))

        self.stop()

    def stop(self):
        """
        Set the stopCondition to stop so that no new execution will be scheduled.
        The running executions will not be interrupted
        """
        self.stopCondition = True

    def run_next_flow(self):
        c = LoadThread(target=self.flow, args=self.args)
        c.start()
        self.active.append(c)
        self.calls["Started"] += 1

    def monitor(self, max_tracked_errors=30):
        while self.active or not self.stopCondition:
            sleep(0.1)
            for inst in (ins for ins in self.active if not ins.is_alive()):
                try:
                    inst.join()
                except Exception as e:
                    key = str(e)
                    if ": Got" in key:
                        key = key.split('"')[1]
                    key = "Failed: " + key
                    if key in self.calls:
                        self.calls[key] += 1
                    elif len(self.calls) < max_tracked_errors:
                        self.calls[key] = 1
                else:
                    self.calls["Passed"] += 1
                finally:
                    self.active.remove(inst)
                    self.calls["Finished"] += 1
        self.loop.join()

    def statistics(self):
        self.calls["Active"] = len(self.active)
        self.log.info("{}:{}".format(time(), self.calls))
        if not self.stopCondition and (self.duration < 0 or time() - self.startTime < self.duration) or self.active:
            Timer(1, self.statistics).start()
        else:
            print("STOPPING")


class LoadThread(Thread):
    """ I had to make a custom thread class to handle exceptions """

    def run(self):
        self.exc = False
        try:
            super().run()
        except Exception as e:
            self.exc = e
            logger.debug("Exception in Thread: " + self.name)
            logger.debug(traceback.format_exc())
            raise

    def join(self, timeout=None):
        super().join(timeout)
        if self.exc:
            raise self.exc
