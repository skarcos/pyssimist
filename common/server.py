"""\
Purpose: Network connection facilities - mock servers
Initial Version: Costas Skarakis 16/2/2020
"""
import selectors
import socket
import threading
import types

import common.client as my_clients
from csta.CstaApplication import CstaApplication
from csta.CstaParser import parseBytes
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
        self.handlers = {}
        self.handlers_args = {}

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
                    else:
                        self.service_connection(key, mask)
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

    def on(self, incoming_message_type, action, args=()):
        """
        Define a response action to a trigger received message

        :param incoming_message_type: The trigger message
        :param action: A function to call when this message is received.
                    The first argument of this function
        :param args: Optional positional arguments to pass to action starting from 3rd position
        """
        self.handlers[incoming_message_type] = action
        self.handlers_args[incoming_message_type] = args

    def service_connection(self, key, mask):
        pass


class CstaServer(SipServer):
    def __init__(self, ip, port, protocol="tcp"):
        super().__init__(ip, port, protocol)
        self.name = "PythonCstaServer"
        self.refid = 0
        self.csta_endpoint = CstaApplication()
        self.csta_endpoint.parameters = {self.name: {"eventid": 1}}
        self.send = self.csta_endpoint.send
        self.wait_for_csta_message = self.csta_endpoint.wait_for_csta_message
        self.wait_for = self.csta_endpoint.wait_for_csta_message
        self.on("MonitorStart", self.monitor_user)
        self.on("SystemStatus", self.system_status)
        self.on("SystemRegister", self.system_register)
        self.on("SnapshotDevice", self.snapshot_device)

    def on(self, incoming_message_type, action, args=()):
        super().on(incoming_message_type, action, args)
        self.csta_endpoint.set_auto_answer(incoming_message_type)

    def set_parameter(self, user, key, value):
        self.csta_endpoint.parameters[user][key] = value

    def accept_wrapper(self, sock):
        conn, addr = sock.accept()  # Should be ready to read
        print("accepted connection from", addr)
        conn.setblocking(False)
        data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
        events = selectors.EVENT_READ #| selectors.EVENT_WRITE
        self.sel.register(conn, events, data=data)
        self.make_client(conn, addr)
        self.csta_endpoint.parameters[self.name]["systemStatus"] = "enabled"
        self.csta_endpoint.parameters[self.name]["sysStatRegisterID"] = self.name
        self.csta_endpoint.send(from_user=self.name, to_user=None, message="SystemStatus")
        self.csta_endpoint.wait_for_csta_message(for_user=self.name, message="SystemStatusResponse")
        self.csta_endpoint.parameters[self.name]["eventid"] = 0

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
        self.csta_endpoint.link = client
        self.csta_endpoint.link.socket = sock
        #        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.csta_endpoint.link.sockfile = sock.makefile(mode='rb')
        return client

    def service_connection(self, key, mask):
        sock = key.fileobj
        data = key.data
        if mask & selectors.EVENT_READ:
            # print("ready to read")
            inbytes = self.csta_endpoint.link.waitForCstaData(timeout=5.0)
            inmessage = parseBytes(inbytes)
            self.csta_endpoint.message_buffer.append(inmessage)
            self.handlers[inmessage.event](self, inmessage, *self.handlers_args[inmessage.event])
        if mask & selectors.EVENT_WRITE:
            # print("ready to write")
            if data.outb:
                print("echoing", repr(data.outb), "to", data.addr)
                sent = sock.send(data.outb)  # Should be ready to write
                data.outb = data.outb[sent:]

    @staticmethod
    def monitor_user(self, monitor_message):
        user = monitor_message["deviceObject"]
        self.csta_endpoint.parameters[user] = {"eventid": 1,
                                               "deviceID": user,
                                               "CSTA_CREATE_MONITOR_CROSS_REF_ID": self.refid,
                                               "CSTA_USE_MONITOR_CROSS_REF_ID": self.refid}
        self.refid += 1
        self.wait_for_csta_message(for_user=user, message="MonitorStart", new_call=True)
        self.send("MonitorStartResponse", from_user=user)

    @staticmethod
    def system_register(self, system_register_message):
        self.csta_endpoint.parameters[self.name]["sysStatRegisterID"] = self.name
        self.csta_endpoint.wait_for_csta_message(for_user=self.name, message="SystemRegister", new_call=True)
        self.csta_endpoint.send(from_user=self.name, to_user=None, message="SystemRegisterResponse")

    @staticmethod
    def system_status(self, system_status_message):
        self.csta_endpoint.parameters[self.name]["systemStatus"] = "normal"
        self.csta_endpoint.wait_for_csta_message(for_user=self.name, message="SystemStatus", new_call=True)
        self.csta_endpoint.send(from_user=self.name, to_user=None, message="SystemStatusResponse")

    @staticmethod
    def snapshot_device(self, snapshot_device_message):
        self.csta_endpoint.wait_for_csta_message(for_user=self.name, message="SnapshotDevice", new_call=True)
        self.csta_endpoint.send(from_user=self.name, to_user=None, message="SnapshotDeviceResponse")
