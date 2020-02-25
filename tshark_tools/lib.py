"""\
Utility functions to work with "wireshark" network capture files

Initial Version: Costas Skarakis 23/2/2020
"""
import os.path
import platform
import re
import subprocess as sb
import json

from sip.SipMessage import SipMessage


def open_cap_file(filename, tshark_path):
    if not tshark_path:
        print("tshark_path not provided. Program installation path must exist in PATH environment variable")
        tshark = "tshark"
    else:
        tshark = os.path.join(tshark_path, "tshark")
    if " " in tshark:
        tshark = '"' + tshark + '"'
    out, err = sb.Popen(tshark + " -r " + filename + " -T json > traceoutput.json",
                        shell=True, stdout=sb.PIPE, stderr=sb.PIPE).communicate()
    if out:
        print(out)
    if err:
        print(err)
    return os.path.join(".", "traceoutput.json")


def get_from_cap_file(filename, tshark_path=""):
    """
    Read a tethereal/tshark/wireshark file and return all the messages as a list of strings
    Requires tshark installed.

    :param filename:  the name of file (pcapng content)
    :param tshark_path: the location of tshark.
    :return: a list of messages as a list of strings
    """
    j_output = open_cap_file(filename, tshark_path)
    return get_sip_from_json_file(j_output)


def get_sip_from_json_file(filename):
    """
    Read a tethereal/tshark/wireshark file and return all the messages as a list of strings
    Requires tshark installed.

    :param filename:  the name of file (json content)
    :return: a list of messages as a list of strings
    """
    with open(filename, "rb") as j_file:
        j_obj = json.load(j_file)
    result = []
    for j_msg in j_obj:
        try:
            this_msg = ""

            if "sip.Request-Line" in j_msg["_source"]["layers"]["sip"].keys():
                this_msg += j_msg["_source"]["layers"]["sip"]["sip.Request-Line"]

            elif "sip.Status-Line" in j_msg["_source"]["layers"]["sip"].keys():
                this_msg += j_msg["_source"]["layers"]["sip"]["sip.Status-Line"]

            this_msg += '\r\n'
            # this seems to include the body as well, at least in trace with notify messages with xml bodies
            this_msg += j_msg["_source"]["layers"]["sip"]["sip.msg_hdr"]

            # if "sip.msg_body" in j_msg["_source"]["layers"]["sip"].keys():
            #     body = "".join(j_msg["_source"]["layers"]["sip"]["sip.msg_body"].keys())
            #     this_msg += body.replace(r"\\r\\n", "\r\n")

            result.append(this_msg)
        except KeyError:
            continue
    return result


def make_sip_message_template(sip_message):
    """
    Takes a SipMessage instance and returns a string with all dynamic elements removed and replaced with placeholders
    :param sip_message: The SipMessage instance or a sip message as string
    :return: A string template
    """
    if isinstance(sip_message, str):
        contents = sip_message
    elif isinstance(sip_message, SipMessage):
        contents = sip_message.contents()
    else:
        print("Invalid sip message type", type(sip_message))
        return -1
    replacements = {r"Call-ID: .*": "Call-ID: {callId}",
                    r"sip:.*@[\w\d\.]+:\d+": r"sip:{user}@{dest_ip}:{dest_port}",
                    r"sip:.*@[\w\d\.]+": r"sip:{user}@{dest_ip}",
                    r": .* <": ": \"{user}\" <",
                    r"transport=\w{3}": "transport={transport}",
                    r"SIP/2\.0/\w{3}": "SIP/2.0/{transport}",
                    r"(From.*)tag=.*": r"\1tag={fromTag}",
                    r"(To.*)tag=.*": r"\1tag={toTag}",
                    r"(Via.*)branch=.*": r"\1branch={viaBranch}",
                    r"CSeq: \d+ ([A-Z]+)": r"CSeq: {cseq} \1",
                    r"Max-Forwards: \d+": r"Max-Forwards: {max_forwards}",
                    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+": r"{ip}:{port}",
                    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}": r"{ip}",
                    r"^([\w-]+): \d+": r"\1: {\1}",
                    r"\d{5,}": "{num}",  # {five_plus_digit_number
                    r"[0-9A-Fa-f]{10,}": "{hash}",  # 10_plus_character_hex_string
                    r"[\d\.-_/\\~]{3,}": "{hash}"  # 3_plus_character_string_with_only_digits_and_special_characters
                    }
    result = ""
    for line in contents.split("\r\n"):
        for item in replacements:
            patrn, rplmnt = item, replacements[item]
            line = re.sub(patrn, rplmnt, line, re.IGNORECASE)
        result += line + "\r\n"
    return result + "\r\n"


def get_msg_list_from_file(trace_file, input_format, tshark_path):
    if not tshark_path and platform.system() == "Windows":
        tshark_path = r"C:\Program Files\Wireshark"
    if input_format == "pcapng":
        list1 = get_from_cap_file(filename=trace_file, tshark_path=tshark_path)
    elif input_format == "json":
        list1 = get_sip_from_json_file(filename=trace_file)
    else:
        print("Invalid input file type: {}. Supported formats are pcapng and json".format(input_format))
        return None
    return list1


def summarize_trace(filename, applications=("sip", "http", "rtp"), tshark_path=None):
    if not tshark_path and platform.system() == "Windows":
        tshark_path = r"C:\Program Files\Wireshark"
    with open(open_cap_file(filename, tshark_path), "rb") as j_file:
        j_obj = json.load(j_file)
    result = {}
    for application in applications:
        result[application] = {"count": 0}
    for j_msg in j_obj:
        frame_protocols = j_msg["_source"]["layers"]["frame"]["frame.protocols"]
        if not any([application in frame_protocols for application in applications]):
            continue
        ip_layer = frame_protocols.split(":")[2]
        transport_layer = frame_protocols.split(":")[3]
        for application in applications:
            if application in j_msg["_source"]["layers"]:
                src_addr = "{}:{}".format(j_msg["_source"]["layers"][ip_layer][ip_layer+".src"],
                                          j_msg["_source"]["layers"][transport_layer][transport_layer + ".srcport"])
                dst_addr = "{}:{}".format(j_msg["_source"]["layers"][ip_layer][ip_layer + ".dst"],
                                          j_msg["_source"]["layers"][transport_layer][transport_layer + ".dstport"])
                result[application].setdefault(ip_layer+":"+transport_layer, set()).add((src_addr, dst_addr))
                result[application]["stream_count"] = len(result[application][ip_layer+":"+transport_layer])
                result[application]["count"] += 1

    return result

