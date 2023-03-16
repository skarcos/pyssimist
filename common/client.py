"""\
Purpose: Network connection facilities
Initial Version: Costas Skarakis 11/11/2018
"""
import selectors
import socket
import ssl
import io
from threading import Lock

from common.tc_logging import debug
from common.util import wait_for_sip_data, NoData, IncompleteData


class TCPClient(object):
    def __init__(self, ip, port):
        self.sip_buffer = []
        self.ip = ip
        self.port = port
        self.rip, self.rport = None, None
        if ":" in self.ip:
            # ipv6 case
            self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.send_lock = Lock()
        self.wait_lock = Lock()
        self.csta_wait_lock = Lock()
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.socket, selectors.EVENT_READ, data=None)

    def connect(self, dest_ip, dest_port):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.ip, self.port))
        self.port = self.socket.getsockname()[1]
        self.socket.settimeout(5.0)
        self.sockfile = self.socket.makefile(mode='rb')

        self.socket.connect((dest_ip, dest_port))
        self.rip = dest_ip
        self.rport = dest_port

    def send(self, data, encoding="utf8"):
        # self.socket.sendall(binascii.hexlify(bytes(data,"utf8")))
        with self.send_lock:
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
        if timeout:
            self.socket.settimeout(timeout)
        try:
            data = self.socket.recv(buffer)
        finally:
            self.socket.settimeout(bkp)
        debug("Received on port {}:\n\n".format(self.port) + data.decode("utf8", "backslashreplace").replace("\r\n",
                                                                                                             "\n"))
        return data

    def wait_select(self, timeout):
        if not self.sel.select(timeout):
            raise socket.timeout("Timeout waiting for data in " + self.ip + ":" + str(self.port))

    def waitForSipData(self, timeout=None, client=None, bufsize=4096):
        if not client:
            client = self
        with client.wait_lock:
            debug("Waiting on port {}".format(client.port))
            bkp = client.socket.gettimeout()
            data = b""
            try:
                if client.sip_buffer:
                    data = client.sip_buffer.pop(0)
                else:
                    client.wait_select(timeout)
                    all_data = io.BytesIO(client.socket.recv(bufsize))
                    while True:
                        try:
                            # There may be more than one sip messages in the socket
                            # I think select will not trigger if we only read one of them
                            # and then come back for the second one
                            client.sip_buffer.append(wait_for_sip_data(all_data))
                            # We will replace all_data with everything following the current
                            # read location to discard the message that was already added to the
                            # buffer.
                            # In case all_data contained more than one message and the second one
                            # was incomplete, we have to reread only the second message
                            # not the first one again which is already in the sip_buffer
                            all_data = io.BytesIO(all_data.read())
                        except EOFError:
                            if client.sip_buffer:
                                data = client.sip_buffer.pop(0)
                                break
                            else:
                                client.wait_select(timeout)
                                all_data = io.BytesIO(client.socket.recv(bufsize))
                                continue
                        except IncompleteData:
                            client.wait_select(timeout)
                            all_data = io.BytesIO(all_data.getvalue() + client.socket.recv(bufsize))
                            continue
                        except NoData:
                            if client.sip_buffer:
                                data = client.sip_buffer.pop(0)
                            else:
                                data = all_data.getvalue()
                                debug('Invalid SIP Data in socket: ' + data.decode())
                                all_data = io.BytesIO(all_data.read())
                                continue
                                # raise ValueError
                            break
            except ValueError:
                debug('Value Error: '+data.decode())
                # debug(line.decode())
                # raise
            except socket.timeout:
                debug('Data received before timeout: "{}"'.format(data.decode()))
                raise
            finally:
                client.socket.settimeout(bkp)
            debug("Received on port {}:\n\n".format(client.port) + data.decode("utf8").replace("\r\n", "\n"))
            return data

    def waitForCstaData(self, timeout=None):
        with self.csta_wait_lock:
            bkp = self.socket.gettimeout()
            if timeout:
                self.socket.settimeout(timeout)
            elif timeout is None:
                self.socket.setblocking(True)
            try:
                # header = ""
                # while not header:
                header = self.socket.recv(4)
                if not header:
                    debug("Csta socket was probably disconnected from the other side")
                    return None
                datalength = int(''.join(["%02X" % x for x in header]), base=16) - 4
                data = b''
                while len(data) < datalength:
                    data += self.socket.recv(datalength - len(data))
                debug(
                    "Received on port {} message of length {}:\n\n".format(self.port, datalength) + (header + data).decode(
                        "utf8",
                        "backslashreplace").replace("\r\n", "\n"))
            except socket.timeout:
                debug('Data received before timeout: "{}"'.format(data.decode()))
                raise
            finally:
                self.socket.settimeout(bkp)
            return header + data

    def shutdown(self):
        self.socket.shutdown(socket.SHUT_RDWR)


class UDPClient(TCPClient):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.rip, self.rport = None, None
        if ":" in self.ip:
            # ipv6 case
            self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.ip, self.port))
        self.socket.settimeout(5.0)
        self.sockfile = self.socket.makefile(mode='rb')
        self.send_lock = Lock()
        self.wait_lock = Lock()
        self.csta_wait_lock = Lock()


class TLSClient(TCPClient):
    def __init__(self, ip, port, certificate=None, subject_name="localhost"):
        self.ip = ip
        self.port = port
        self.rip, self.rport = None, None
        self.server_name = subject_name
        self.send_lock = Lock()
        self.wait_lock = Lock()
        self.csta_wait_lock = Lock()

        # PROTOCOL_TLS_CLIENT requires valid cert chain and hostname
        if hasattr(ssl, "PROTOCOL_TLS_CLIENT"):
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        elif hasattr(ssl, "PROTOCOL_TLSv1_1"):
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
        else:
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)

        if not certificate:
            self.context.check_hostname = False
            self.context.verify_mode = ssl.CERT_NONE
            ssl.create_default_context()
        else:
            # certificate example: 'path/to/my_certificate.pem'
            self.context.load_verify_locations(certificate)

    def connect(self, dest_ip, dest_port):
        if ":" in self.ip:
            # ipv6 case
            tcp_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)
        else:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket = self.context.wrap_socket(tcp_socket, server_hostname=self.server_name)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#        self.socket.bind((self.ip, self.port))
        #self.port = self.socket.getsockname()[1]
        self.socket.settimeout(5.0)
        self.sockfile = self.socket.makefile(mode='rb')
        super().connect(dest_ip, dest_port)
