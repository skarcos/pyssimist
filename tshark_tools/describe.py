import argparse
import pprint
from datetime import datetime
from os import chdir, listdir, path
import sys
from string import ascii_uppercase
sys.path.append("..")
sys.path.append(path.join("..", ".."))
from tshark_tools.lib import get_msg_list_from_file, msg_filter, make_sip_message_template, summarize_trace
from sip.SipParser import buildMessage


def make_sub(i):
    max_letters = len(ascii_uppercase)
    numbering = str(int(i / max_letters))
    if numbering == "0":
        numbering = ""
    suffix = ascii_uppercase[i % max_letters] + numbering
    return "SUB_" + suffix


def get_sub(addr, addr_dict):
    if addr in addr_dict:
        return addr_dict[addr]
    else:
        sub = make_sub(len(addr_dict) + 1)
        addr_dict[addr] = sub
        return sub


def describe(tracefile, filters, wireshark_filter=None, tshark_path=None):
    """
    Describe a network trace as a runnable pyssimist test

    :param tracefile: Input network file in pcapng or json format
    :param wireshark_filter: Unless input is json, apply this wireshark filter to the output
    :param tshark_path: If not in PATH envirnonment variable, the path of the wireshark binaries must be given here
    :param filters: A list of filters to remove noise from messages.

    :return: A pyssimist testcase
    """
    tc_data = "tc_data.py"
    test_py = "test.py"
    if tracefile.endswith("json"):
        i_format = "json"
    else:
        i_format = "pcapng"
    count = 0
    subs = {}
    test_lines = "from tc_data import tc_message\n"
    test_data = {}
    summary = summarize_trace(tracefile, input_format=i_format, tshark_filter=wireshark_filter)
    for transport in summary["sip"]:
        if isinstance(summary["sip"][transport], list):
            for time_epoch, fromaddr, toaddr, message, expand in summary["sip"][transport]:
                a = get_sub(fromaddr, subs)
                b = get_sub(toaddr, subs)
                if "Call-ID" not in filters:
                    filters["Call-ID"] = []
                key = message.get_status_or_method().split()[0] + "_" + str(count)
                if msg_filter(message, filters) is None:
                    if message.type == "Request":
                        filters["Call-ID"].append(message["Call-ID"])
                    continue
                msg_template = make_sip_message_template(message, purpose="testcase")
                if msg_template not in test_data.values():
                    test_data[key] = msg_template
                    count += 1
                test_lines += "{}.send({}, tc_message['{}'])\n".format(a, b, key)
                test_lines += "{}.wait_for_message('{}')\n".format(b, message.get_status_or_method())

    with open(tc_data, "w") as sip_trace:
        sip_trace.write("tc_message = \\\n")
        sip_trace.write(pprint.pformat(test_data, width=200))
    with open(test_py, "w") as sip_test:
        sip_test.write(test_lines)


def GetArgs():
    """
    Supports the command-line arguments listed below.
    """
    parser = argparse.ArgumentParser(description='Summarize network capture file with expanded')
    parser.add_argument('-d', '--directory', required=False, action='store',
                        help='A directory containing the files to analyze')
    parser.add_argument('-i', '--input-file', required=False, action='store',
                        help='A directory containing the files to analyze')
    parser.add_argument('-f', '--filter', required=False, action='store',
                        help='Wireshark filter to apply to output')
    parser.add_argument('-t', '--tshark-path', required=False, action='store',
                        help='Wireshark binaries path. If omitted, it should be included in PATH environment variable]')
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = GetArgs()
    if args.directory:
        chdir(args.directory)
        for file in listdir("."):
            if file.rsplit(".", 1)[-1] in ("pcapng", "pcap", "cap", "json"):
                describe(file, filters={}, tshark_path=args.tshark_path, wireshark_filter=args.filter)
    if args.input_file:
        describe(args.input_file, filters={}, tshark_path=args.tshark_path, wireshark_filter=args.filter)