import socket, binascii
from pprint import pprint

class TCPClient(object):
    def __init__(self,ip,port):
        self.ip=ip
        self.port=port
        self.socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.ip,self.port))
        self.socket.settimeout(5.0)
        
    def connect(self,dest_ip,dest_port):
        self.socket.connect((dest_ip,dest_port))

            
    def send(self,data):
        #self.socket.sendall(binascii.hexlify(bytes(data,"utf8")))
        self.socket.sendall(bytes(data,"utf8"))

    def waitForData(self,buffer=4096):
        data = self.socket.recv(buffer)
        return data
