"""\
Purpose: Network connection facilities
Initial Version: Costas Skarakis 21/6/2019
"""
import sys
from queue import Empty
import socket, select
from traceback import print_exc

from common.tc_logging import debug
import multiprocessing as mp
from sip.SipParser import parseBytes as parseSip, buildMessage as buildSip


class Server(object):
    def __init__(self, server_type, local_addr, remote_addr, in_queue, internal_socket, events_queue):
        self.type = server_type
        self.local_addr = local_addr
        self.remote_addr = remote_addr
        self.queue = in_queue
        self.internal_socket = internal_socket
        self.internal_socket.listen()
        self.events_queue = events_queue
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(local_addr)
        self.sock.settimeout(5.0)
        self.sock.connect(remote_addr)
        self.sockfile = self.sock.makefile(mode='rb')
        self.expected_messages = []
        self.lock = mp.Lock()
        try:
            self.serve()
        except KeyboardInterrupt:
            self.queue.put("Stop")

    def consume_sip_data(self):
        try:
            #debug("reading for sip data")
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
                #debug(data.decode())
                #raise Exception TODO
                print("No content length in message")
        except ValueError:
            debug(data.decode())
            debug(line.decode())
            print_exc()
            #raise
        except socket.timeout:
            #debug('Data received before timeout: "{}"'.format(data.decode()))
            print_exc()
            #raise
        self.handle_sip_message(data)

    def consume_csta_data(self, timeout=None):
        header = self.sock.recv(4)
        datalength = int(''.join(["%02X" % x for x in header]), base=16) - 4
        data = b''
        while len(data) < datalength:
            data += self.sock.recv(datalength - len(data))
        # print('message:\n{}\nsize{}\n'.format(data,datalength))
        return header + data

    def handle_sip_message(self, data, encoding="utf8"):
        self.update_sip_event_handling()
        inmessage = parseSip(data)
        message = inmessage.get_status_or_method()
        dialog = inmessage.get_dialog()
        for msg, dlg, resp in self.expected_messages:
            # If the dialog dlg is {} we will respond to all msg messages received
            if msg == message and (dlg == dialog or dlg == {}):
                if resp:
                    response = buildSip(resp, {})
                    response.make_response_to(inmessage)
                    response.set_transaction_from(inmessage)
                    self.lock.acquire()
                    self.sock.sendall(bytes(response.contents(), encoding))
                    self.lock.release()
                # If no response is given for these messages then they will just be ignored
                return
        self.queue.put(data)

    def update_sip_event_handling(self):
        try:
            # incoming queue object should be <Method or Status>, dialog, response message <string template>
            message, dialog, response = self.events_queue.get_nowait()
            self.expected_messages.append((message, dialog, response))
        except Empty:
            return

    def serve(self):
        inputs = [self.sock, self.internal_socket]
        outputs = []
        message_queues = {}
        while inputs:
            #sleep(0.01)
            readable, writable, exceptional = select.select(inputs, outputs, inputs)
            if exceptional:
                raise Exception("Exception in select")
            for r in readable:
                if r is self.sock:
                    if self.type == "sip":
                        self.consume_sip_data()
                    elif self.type == "csta":
                        self.consume_csta_data()

                elif r is self.internal_socket:
                    connection, client_address = self.internal_socket.accept()
                    inputs.append(connection)
                    message_queues[connection] = mp.Queue()
                else:
                    data = r.recv(1024)
                    self.lock.acquire()
                    self.sock.sendall(data)
                    self.lock.release()

            # for s in writable:
            #     try:
            #         next_msg = message_queues[s].get_nowait()
            #     except Empty:
            #         outputs.remove(s)
            #     else:
            #         self.lock.acquire()
            #         s.sendall(next_msg)
            #         self.lock.release()
            #
            # for s in exceptional:
            #     inputs.remove(s)
            #     if s in outputs:
            #         outputs.remove(s)
            #     s.close()


class TCPClient(object):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.rip = None
        self.rport = None
        self.rip, self.rport = None, None
        self.lock = mp.Lock()
        self.in_queue = mp.Queue()
        self.out_queue = mp.Queue()
        self.internal_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.internal_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.internal_socket.bind(("127.0.0.1", 0))
        self.internal_client = socket.socket()
        self.events_queue = mp.Queue()
        self.server = None
        # self.buffer = []
        self.endpoints_connected = 0

    def connect(self, dest_ip, dest_port):
        self.rip = dest_ip
        self.rport = dest_port
        self.server = self.start_server("sip")

    def start_server(self, server_type):
        """ Start a server process """
        server = mp.Process(target=Server, name=str("{}:{}".format(self.ip, self.port)), args=(server_type,
                                                                                         (self.ip,self.port),
                                                                                         (self.rip, self.rport),
                                                                                         self.in_queue,
                                                                                         self.internal_socket,
                                                                                         self.events_queue))
        server.start()
        self.internal_client.connect(self.internal_socket.getsockname())
        return server

    def register_for_event(self, event):
        """ Event should be three-tuple of <Method or Status>, dialog, response message <string template> """
        self.events_queue.put(event)

    def send(self, data, encoding="utf8"):
        # try:
        #     data = self.out_queue.get_nowait()
        # except Empty:
        #     return
        if type(data) == type(b''):
            debug("Sending from port {}:\n\n".format(self.port) + data.decode("utf8", "backslashreplace").replace(
                "\r\n", "\n"))
            self.internal_client.sendall(data)
        else:
            debug("Sending from port {}:\n\n".format(self.port) + data.replace("\r\n", "\n"))
            self.internal_client.sendall(bytes(data, encoding))

    def waitForSipData(self, timeout=5):
        if not self.server:
            self.start_server("sip")
        try:
            return self.wait_for_data(timeout)
        except Empty:
            raise TimeoutError("Timeout waiting for message on {}:{}".format(self.ip, self.port))

    def waitForCstaData(self, timeout=5):
        if not self.server:
            self.start_server("csta")
        return self.wait_for_data(timeout)

    def wait_for_data(self, timeout=None):
        debug("Waiting on address {}:{}".format(self.ip, self.port))
        try:
            data = self.in_queue.get(timeout=timeout)
            if data == "Stop":
                raise KeyboardInterrupt
        except Empty:
            debug("No message received after timeout")
            raise
        if isinstance(data, tuple):
            dbg = data[0]
        else:
            dbg = data
        debug("Received on address {}:{}:\n\n".format(self.ip, self.port) + dbg.decode("utf8").replace("\r\n", "\n"))
        return data



class UDPClient(TCPClient):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.rip, self.rport = None, None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.ip, self.port))
        self.socket.settimeout(5.0)
        self.sockfile = self.socket.makefile(mode='rb')

if __name__ == "__main__":
    from sip.messages import message
    lip = "10.114.72.154"
    A = TCPClient(lip, 41141)
    A.connect(lip, 8000)
    A.send(b'''GET / HTTP/1.1
Host: localhost:8000
User-Agent: Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
Connection: keep-alive
Upgrade-Insecure-Requests: 1

''')
    A.register_for_event(("200 OK", {}, message["200_OK_Notify"]))
    A.waitForSipData()
