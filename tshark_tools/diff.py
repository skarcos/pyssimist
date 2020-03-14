import argparse
from datetime import datetime
import pprint
from os import chdir, listdir
from os import path
import sys
sys.path.append("..")
sys.path.append(path.join("..", ".."))
from tshark_tools.lib import summarize_trace


def analyze(tracefile, *criteria, wireshark_filter=None):
    outfile = tracefile.rsplit(".", 1)[0]+".txt"
    if tracefile.endswith("json"):
        i_format = "json"
    else:
        i_format = "pcapng"
    print(criteria)
    summary = summarize_trace(tracefile, *criteria, input_format=i_format, tshark_filter=wireshark_filter)

    output = "TraceFile: " + tracefile
    output += "\nExpanding messages matching:\n"
    for criterion in criteria:
        output += pprint.pformat(criterion)
        output += "\n"
    output += "\n\n\n"
    calls = []
    for transport in summary["sip"]:
        if isinstance(summary["sip"][transport], list):
            for time_epoch, fromaddr, toaddr, message, expand in summary["sip"][transport]:
                timestamp = datetime.fromtimestamp(float(time_epoch)).strftime("%Y-%m-%dT%H:%M:%S.%f")
                try:
                    callid = message["Call-ID"]
                except:
                    print(message.contents())
                    raise
                if callid not in calls:
                    calls.append(callid)
                call_number = calls.index(callid) + 1
                m_lines = message.contents().split("\r\n")
                o_line = "{} | Call#{:0>4}: {:20} {:-^14}> {:20} | {}\n".format(timestamp, call_number, fromaddr, transport, toaddr, m_lines[0])
                output += o_line
                if expand:
                    for m_line in m_lines[1:]:
                        output += ("{:" + str(len(o_line.rsplit("|", 1)[0])+2) + "}{}\n").format(" ", m_line)
    with open(outfile, "w") as sip_trace:
        sip_trace.write(output)
    return outfile


def GetArgs():
    """
    Supports the command-line arguments listed below.
    """
    parser = argparse.ArgumentParser(description='Summarize network capture file with expanded')
    parser.add_argument('-d', '--directory', required=False, action='store',
                        help='The directory containing the files to analyze')
    parser.add_argument('-f', '--filter', required=False, action='store',
                        help='Wireshark filter to apply to output')
    parser.add_argument('-m', '--message', required=False, action='store',
                        help='Expand SIP messages whose Request URI or Status Code contain this string')

    args = parser.parse_args()
    return args

if __name__ == "__main__":
    # diff(ref_trace="reference.json", check_trace="traceoutput.json", input_format="json")
    ignore = {"Message": ["OPTIONS"]}

    # diff(ref_trace="simclientsip_side.pcapng", check_trace="bcfe.pcap", input_format="pcapng", filters=ignore)

    Test0 = {"xml": {"any": "ns:recording",
                     "label tag": "audio",
                     "nameID aor attr": "sip:912119@grtsep41l3n1sipsm.h8k.sec"}
             }

    TestKat1 = {"Message": "INVITE",
                "Headers": {"Call-Info": "eidd"}
                }
    TestKat2 = {"Message": "REFER",
                "Headers": {"Refer-To": "eidd"},
                }

    Test1 = {"Headers": {"From": "302200880895"}
             }
    Test2 = {"Message": "404 Not Found"
             }
    # check_in_trace(TestKat1, TestKat2, check_trace="bcf_e_selective.pcap")

    #ignore = {"Message": ["OPTIONS", "SUBSCRIBE"]}
    # diff(ref_trace="bcf_egress_comfort_noise_enabled.pcap", check_trace="bcf_e_selective.pcap", input_format="pcapng", filters=ignore)

    # pprint(summarize_trace("bcf_egress_comfort_noise_enabled.pcap"))

    args = GetArgs()
    chdir(args.directory)
    for file in listdir("."):
        if file.rsplit(".", 1)[-1] in ("pcapng", "pcap", "cap", "json"):
            analyze(file, Test1, Test2, wireshark_filter=args.filter)
