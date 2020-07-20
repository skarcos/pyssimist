"""\
Purpose:
Initial Version: Costas Skarakis 7/11/2020  
"""
from common.server import CstaServer
from csta.CstaApplication import CstaApplication
from csta.CstaEndpoint import CstaEndpoint
import time

if __name__ == "__main__":
    HOST, PORT = "localhost", 9999
    MockCSTATCP = CstaServer(HOST, PORT)
    MockCSTATCP.serve_in_background()
    A = CstaApplication()
    A.connect(("localhost", 6666),
              (HOST, PORT),
              "tcp")
    time.sleep(2)
    MockCSTATCP.shutdown()
