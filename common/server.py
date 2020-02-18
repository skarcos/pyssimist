"""\
Purpose: Network connection facilities - mock servers
Initial Version: Costas Skarakis 16/2/2020
"""
import socket
import types

import common.client as my_clients
import selectors
import threading
from sip.SipEndpoint import SipEndpoint


# With help from https://github.com/realpython/materials/blob/master/python-sockets-tutorial/multiconn-server.py
from sip.SipParser import parseBytes


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
        self.sip_endpoint = SipEndpoint.SipEndpoint("PythonSipServer")

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


if __name__ == "__main__":
    from sip import SipEndpoint
    from sip.messages import message
    import time
    HOST, PORT = "localhost", 9999
    MockSIPTCP = SipServer(HOST, PORT)
    MockSIPTCP.serve_in_background()
    A = SipEndpoint.SipEndpoint("121242124")
    B = MockSIPTCP.sip_endpoint
    A.connect(("localhost", 6666),
              (HOST, PORT),
              "tcp")
    A.send_new(B, message["Register_1"])
    time.sleep(2)
    B.wait_for_message("REGISTER")
    B.reply(message["200_OK_1"])
    A.wait_for_message("200 OK")
    A.send_new(B, message["Invite_SDP_1"])
    B.wait_for_message("INVITE")
    B.reply(message["200_OK_SDP_1"])
    A.wait_for_message("200 OK")
    B.send(message["Bye_1"])
    A.wait_for_message("BYE")
    # unfortunately our server is not a real sip server yet so there may be some
    # inconsistencies in the dialog elements. Either that or we should make our message pool better
    last_dialog = A.reply(message["200_OK_1"]).get_dialog()
    B.wait_for_message("200 OK", dialog=last_dialog)
    MockSIPTCP.shutdown()

    # def service_connection(self, key, mask):
    #     sock = key.fileobj
    #     data = key.data
    #     if mask & selectors.EVENT_READ:
    #         # recv_data = sock.recv(1024)  # Should be ready to read
    #         try:
    #             inbytes = self.sip_endpoint.link.waitForSipData()
    #             self.sip_endpoint.message_buffer.append(parseBytes(inbytes))
    #             print("got")
    #             print(inbytes.decode("utf-8").split()[0])
    #             self.sel.unregister(sock)
    #             # sock.close()
    #         except my_clients.NoData:
    #             print("closing connection to", data.addr)
    #             self.sel.unregister(sock)
    #             sock.close()
    #     if mask & selectors.EVENT_WRITE:
    #         if data.outb:
    #             self.sip_endpoint.send(data)
