from tc_data import parameters

try:
    from tc_data import tc_message
except:
    pass
from tc_logging import debug, info, warning, error, critical, exception
from sip.messages import message
from sip.SipEndpoint import SipEndpoint
from time import sleep


def setup():
    sip_server_address = (parameters["dest_ip"], parameters["dest_port"])
    # ConnectionPool = [("10.2.31.5", 13001), ("10.2.31.5", 13001)]
    ConnectionPool = [(parameters["local_ip"], parameters["base_local_port"] + i) for i in
                      range(parameters["number_of_endpoints"])]
    global B, C
    #A = SipEndpoint("7867102022")
    B = SipEndpoint("7867112022")
    C = SipEndpoint("7867122022")
    #A.parameters.update(parameters)
    B.parameters.update(parameters)
    C.parameters.update(parameters)
    #debug(A.parameters)
    debug(C.parameters)

    #A.connect(ConnectionPool[0], sip_server_address, parameters["transport"])
    B.connect(ConnectionPool[1], sip_server_address, parameters["transport"])
    C.use_link(B.link)

    # C.link = B.link
    # C.ip = B.ip
    # C.port = B.port
    # C.parameters["source_ip"] = B.parameters["source_ip"]
    # C.parameters["source_port"] = B.parameters["source_port"]
    # C.parameters["dest_ip"] = B.parameters["dest_ip"]
    # C.parameters["dest_port"] = B.parameters["dest_port"]
    # C.parameters["transport"] = B.parameters["transport"]

    #A.register()
    B.register()
    C.register()


def cleanup():
    #A.unregister()
    B.unregister()
    C.unregister()


def sip_flow():
    dialogs = {}
    for user in (B, C):
        dialogs["dialog" + str(user)] = user.send_new(message_string=tc_message["Subscribe"]).get_dialog()
        user.waitForMessage("200 OK")
        user.waitForMessage("NOTIFY")  # change to wait for event set
        user.reply(tc_message["200_OK_1"], dialog = dialogs["dialog" + str(user)])
    debug(dialogs)
    for user in (B, C):
        user.send(message_string=tc_message["reSubscribe"])
        user.waitForMessage("200 OK")
        user.waitForMessage("NOTIFY")  # change to wait for event set
        user.reply(tc_message["200_OK_1"], dialog = dialogs["dialog" + str(user)])




if __name__ == "__main__":
    try:
        setup()
    except:
        exception("***ERROR in setup")

    try:
        sip_flow()
        info("NUMBER.OF.NOT.FAILED.CALLS:1")
        info("NUMBER.OF.FAILED.CALLS:0")
        info("SUCCESSFULEXITING")
    except:
        exception("***ERROR in SIP_FLOW")

    try:
        cleanup()
    except:
        exception("***ERROR in Clean-up")
