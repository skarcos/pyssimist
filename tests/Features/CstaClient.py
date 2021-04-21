"""\
Purpose:
Initial Version: Costas Skarakis 8/14/2020  
"""
import threading

from csta.CstaApplication import CstaApplication
from tests.Features.MockCSTATCP import MakeCall

HOST, PORT = "localhost", 9999

A = CstaApplication()
A.connect(("localhost", 0),
          (HOST, PORT),
          "tcp")
u1000 = A.new_user("1000")
u1001 = A.new_user("1001")
u1000.monitor_start()
u1001.monitor_start()
u1002 = A.new_user("1002")
u1003 = A.new_user("1003")
u1002.monitor_start()
u1003.monitor_start()
firstcall = threading.Thread(target=MakeCall, args=(u1000, u1001, 10))
firstcall.start()
secondcall = threading.Thread(target=MakeCall, args=(u1002, u1003, 10))
secondcall.start()
firstcall.join()
secondcall.join()
# A.link.socket.close()
