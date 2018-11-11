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
        self.socket.bind((self.ip, self.port))
        self.socket.settimeout(5.0)

    def connect(self, dest_ip, dest_port):
        self.socket.connect((dest_ip, dest_port))
        self.rip = dest_ip
        self.rport = dest_port

    def send(self, data, encoding="utf8"):
        # self.socket.sendall(binascii.hexlify(bytes(data,"utf8")))
        print(data)
        if type(data) == type(b''):
            self.socket.sendall(data)
            debug("Sent:\n\n" + data.decode("utf8", "backslashreplace").replace("\r\n", "\n"))
        else:
            self.socket.sendall(bytes(data, encoding))
            debug("Sent:\n\n" + data.replace("\r\n", "\n"))

    def waitForData(self, timeout=None, buffer=4096):
        bkp = self.socket.gettimeout()
        if timeout: self.socket.settimeout(timeout)
        try:
            data = self.socket.recv(buffer)
        finally:
            self.socket.settimeout(bkp)
        debug("Received:\n\n" + data.decode("utf8", "backslashreplace").replace("\r\n", "\n"))
        return data

    def waitForCstaData(self):
        header = self.socket.recv(4)
        datalength = int(''.join(["%02X" % x for x in header]), base=16) - 4
        data = b''
        while len(data) < datalength:
            data += self.socket.recv(datalength - len(data))
        # print('message:\n{}\nsize{}\n'.format(data,datalength))
        debug("Received:\n\n" + data.decode("utf8", "backslashreplace").replace("\r\n", "\n"))
        return header + data
