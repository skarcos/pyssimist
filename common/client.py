"""\
Purpose: Network connection facilities
Initial Version: Costas Skarakis 11/11/2018
"""
import socket
from common.tc_logging import debug


class TCPClient(object):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.rip, self.rport = None, None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.ip, self.port))
        self.socket.settimeout(5.0)
        self.sockfile = self.socket.makefile(mode='rb')

    def connect(self, dest_ip, dest_port):
        self.socket.connect((dest_ip, dest_port))
        self.rip = dest_ip
        self.rport = dest_port

    def send(self, data, encoding="utf8"):
        # self.socket.sendall(binascii.hexlify(bytes(data,"utf8")))
        if type(data) == type(b''):
            self.socket.sendall(data)
            debug("Sent from port {}:\n\n".format(self.port) + data.decode("utf8", "backslashreplace").replace("\r\n",
                                                                                                               "\n"))
        else:
            self.socket.sendall(bytes(data, encoding))
            debug("Sent from port {}:\n\n".format(self.port) + data.replace("\r\n", "\n"))

    def waitForData(self, timeout=None, buffer=4096):
        debug("Waiting on port {}".format(self.port))
        bkp = self.socket.gettimeout()
        if timeout: self.socket.settimeout(timeout)
        try:
            data = self.socket.recv(buffer)
        finally:
            self.socket.settimeout(bkp)
        debug("Received:\n\n" + data.decode("utf8", "backslashreplace").replace("\r\n", "\n"))
        return data

    def waitForSipData(self, timeout=None):
        debug("Waiting on port {}".format(self.port))
        bkp = self.socket.gettimeout()
        if timeout: self.socket.settimeout(timeout)
        try:
            content_length = -1
            data = b""
            data += self.sockfile.readline()

            while True:
                line = self.sockfile.readline()
                data += line
                if not line.strip():
                    break
                header, value = [x.strip() for x in line.split(b":", 1)]
                if header == b"Content-Length":
                    content_length = int(value)

            if content_length > 0:
                data += self.sockfile.read(content_length)

            if content_length == -1:
                debug(data.decode())
                raise Exception("No content length in message")
        except ValueError:
            debug(data.decode())
            debug(line.decode())
            raise
        except socket.timeout:
            debug('Data received before timeout: "{}"'.format(data.decode()))
            raise
        finally:
            self.socket.settimeout(bkp)
        debug("Received:\n\n" + data.decode("utf8").replace("\r\n", "\n"))
        return data

    def waitForCstaData(self):
        header = self.socket.recv(4)
        datalength = int(''.join(["%02X" % x for x in header]), base=16) - 4
        data = b''
        while len(data) < datalength:
            data += self.socket.recv(datalength - len(data))
        # print('message:\n{}\nsize{}\n'.format(data,datalength))
        debug("Received:\n\n" + (header + data).decode("utf8", "backslashreplace").replace("\r\n", "\n"))
        return header + data


class UDPClient(TCPClient):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.rip, self.rport = None, None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.ip, self.port))
        self.socket.settimeout(5.0)
        self.sockfile = self.socket.makefile(mode='rb')

    def connect(self, dest_ip, dest_port):
        """ UDP doesn't connect so this just sets the instance variables """
        self.rip = dest_ip
        self.rport = dest_port

