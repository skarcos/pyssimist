"""\
Purpose:
Initial Version: Costas Skarakis 7/11/2020  
"""
from common.server import CstaServer
from tc_data import tc_message


def HandleAgentState(csta_server, message):
    user = message["device"]
    csta_server.wait_for_csta_message(for_user=user, message="GetAgentState")
    csta_server.set_parameter(user=user, key="agentID", value=user)
    csta_server.send(tc_message["GetAgentStateResponse"], from_user=user)


if __name__ == "__main__":
    HOST, PORT = "localhost", 1040
    MockCSTATCP = CstaServer(HOST, PORT)
    MockCSTATCP.serve_in_background()
    MockCSTATCP.on("GetAgentState", HandleAgentState)
