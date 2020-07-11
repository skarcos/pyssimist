"""\
Purpose: Network connection facilities - mock servers
Initial Version: Costas Skarakis 16/2/2020
"""
import selectors
import socket
import threading

import common.client as my_clients
from csta.CstaEndpoint import CstaEndpoint
from sip.SipEndpoint import SipEndpoint


# With help from https://github.com/realpython/materials/blob/master/python-sockets-tutorial/multiconn-server.py


class SipServer:
    """
    A simple server to send and receive SIP Messages
    """

    def __init__(self, ip, port, protocol="tcp"):
        self.ip = ip
        self.port = port
        self.protocol = protocol
        self.continue_serving = False
        self.sel = selectors.DefaultSelector()
        if protocol in ("tcp", "TCP"):
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        elif protocol in ("udp", "UDP"):
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        elif protocol in ("tls", "TLS"):
            # for MTLS this might be needed
            # context.load_cert_chain('/path/to/certchain.pem', '/path/to/private.key')
            raise NotImplemented
        self.server_thread = None
        self.sip_endpoint = SipEndpoint("PythonSipServer")

    def accept_wrapper(self, sock):
        conn, addr = sock.accept()  # Should be ready to read
        print("accepted connection from", addr)
        #conn.setblocking(False)
        #data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
        #events = selectors.EVENT_READ | selectors.EVENT_WRITE
        #self.sel.register(conn, events, data=data)
        self.make_client(conn, addr)

    def make_client(self, sock, addr):
        local_ip, local_port = sock.getsockname()
        client = None
        if self.protocol in ("tcp", "TCP"):
            client = my_clients.TCPClient(local_ip, local_port)
        elif self.protocol in ("udp", "UDP"):
            client = my_clients.UDPClient(local_ip, local_port)
        elif self.protocol in ("tls", "TLS"):
            client = my_clients.TLSClient(local_ip, local_port, None)
        client.rip = addr[0]
        client.rport = addr[1]
        self.sip_endpoint.use_link(client)
        self.sip_endpoint.link.socket = sock
        #        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sip_endpoint.link.sockfile = sock.makefile(mode='rb')

        return client

    def serve_forever(self):
        self.socket.bind((self.ip, self.port))
        self.socket.listen()
        self.port = self.socket.getsockname()[1]
        print("listening on", (self.ip, self.port))
        self.socket.setblocking(False)
        self.sel.register(self.socket, selectors.EVENT_READ, data=None)
        self.continue_serving = True
        while self.continue_serving:
            try:
                events = self.sel.select(timeout=5)
                for key, mask in events:
                    if key.data is None:
                        self.accept_wrapper(key.fileobj)
                    # else:
                    #     self.service_connection(key, mask)
            except socket.timeout:
                continue

        self.sel.close()

    def shutdown(self):
        print("Shutting down server. It may take up to 5 seconds")
        self.continue_serving = False
        self.server_thread.join()

    def serve_in_background(self):
        self.server_thread = threading.Thread(target=self.serve_forever)
        self.server_thread.daemon = False
        self.server_thread.start()


class CstaServer(SipServer):
    def __init__(self, ip, port, protocol="tcp"):
        super().__init__(ip, port, protocol)
        self.csta_endpoint = CstaEndpoint("PythonCstaServer")

    def accept_wrapper(self, sock):
        conn, addr = sock.accept()  # Should be ready to read
        print("accepted connection from", addr)
        self.make_client(conn, addr)
        self.csta_endpoint.csta_links.append(self.sip_endpoint.link)
        self.csta_endpoint.parameters["systemStatus"] = "normal"
        self.csta_endpoint.parameters["sysStatRegisterID"] = "PythonCstaServer"
        self.csta_endpoint.send_csta("SystemStatus")
        self.csta_endpoint.wait_for_csta_message("SystemStatusResponse")
        self.csta_endpoint.eventid = 0
        self.csta_endpoint.wait_for_csta_message("SystemRegister")
        self.csta_endpoint.send_csta("SystemRegisterResponse")

    def make_client(self, sock, addr):
        local_ip, local_port = sock.getsockname()
        client = None
        if self.protocol in ("tcp", "TCP"):
            client = my_clients.TCPClient(local_ip, local_port)
        elif self.protocol in ("udp", "UDP"):
            client = my_clients.UDPClient(local_ip, local_port)
        elif self.protocol in ("tls", "TLS"):
            client = my_clients.TLSClient(local_ip, local_port, None)
        client.rip = addr[0]
        client.rport = addr[1]
        self.csta_endpoint.csta_links.append(client)
        self.csta_endpoint.csta_links[0].socket = sock
        #        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.csta_endpoint.csta_links[0].sockfile = sock.makefile(mode='rb')

        return client