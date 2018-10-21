import socket
from time import sleep

class TCPClient(object):
    def __init__(self,ip,port):
        self.ip=ip
        self.port=port
        self.socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.ip,self.port))
        self.socket.settimeout(5.0)
        
    def connect(self,dest_ip,dest_port):
        self.socket.connect((dest_ip,dest_port))

            
    def send(self,data,encoding="utf8"):
        #self.socket.sendall(binascii.hexlify(bytes(data,"utf8")))
        if type(data)==type(b''):
            self.socket.sendall(data)
        else:
            self.socket.sendall(bytes(data,encoding))

    def waitForData(self,buffer=4096):
        data = self.socket.recv(buffer)
        return data

    def waitForCstaData(self):
        header = self.socket.recv(4)
        datalength = int(''.join( [ "%02X" % x  for x in header ] ),base=16)-4
        data=b''
        while len(data) < datalength:
            data+=self.socket.recv(datalength - len(data))
        #print('message:\n{}\nsize{}\n'.format(data,datalength))
        return header+data
