"""\
Purpose:
Initial Version: Costas Skarakis 7/11/2020  
"""
from common.server import SipServer
from sip.SipEndpoint import SipEndpoint
from sip.messages import message
import time

if __name__ == "__main__":

    HOST, PORT = "localhost", 9999
    MockSIPTCP = SipServer(HOST, PORT)
    MockSIPTCP.serve_in_background()
    A = SipEndpoint("121242124")
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
