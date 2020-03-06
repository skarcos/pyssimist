from datetime import datetime
import pprint

from tshark_tools.lib import diff, check_in_trace, summarize_trace

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
    wireshark_filter = "not ip.addr == 127.0.0.1"
    tracefile = "bcf_e_selective.pcap"
    #summary = summarize_trace(tracefile, TestKat1, TestKat2, tshark_filter=wireshark_filter)
    summary = summarize_trace("merged.cap", Test1, Test2, input_format="pcapng", tshark_filter="sip")
    # pprint(summary)
    output = "TraceFile: " + tracefile
    output += "\nExpanding messages matching:\n"
    output += pprint.pformat(TestKat1)
    output += "\n"
    output += pprint.pformat(TestKat2)
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
    print(output)
    with open("bcf_e_selective.txt", "w") as sip_trace:
        sip_trace.write(output)