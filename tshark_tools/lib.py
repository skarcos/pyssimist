"""\
Utility functions to work with "wireshark" network capture files

Initial Version: Costas Skarakis 23/2/2020
"""
import os.path
import platform
import re
import subprocess as sb
import json
from difflib import Differ
from pprint import pprint

from common.util import XmlBody
from sip.SipMessage import SipMessage
from sip.SipParser import buildMessage

replacement_set = {"diff": {r"Call-ID: .*": "Call-ID: {callId}",
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
                            r"[\d\.-_/\\~]{3,}": "{hash}"
                            # 3_plus_character_string_with_only_digits_and_special_characters
                            },
                   "testcase": {r"Call-ID: .*": "Call-ID: {callId}",
                                r"To: \".*\" <sip:.*@[\w\d\.]+:\d+": r"To: \"{userB}\" <sip:{userB}@{dest_ip}:{dest_port}",
                                r"To: <sip:.*@[\w\d\.]+": r"To: <sip:{userB}@{dest_ip}",
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
                                }
                   }


def open_cap_file(filename, tshark_path, tshark_filter=None):
    outfile = filename.rsplit(".", 1)[0] + ".json"
    if not tshark_path:
        print("tshark_path not provided. Program installation path must exist in PATH environment variable")
        tshark = "tshark"
    else:
        tshark = os.path.join(tshark_path, "tshark")
    if " " in tshark:
        tshark = '"' + tshark + '"'
    if tshark_filter:
        filter = "-Y \"{}\"".format(tshark_filter)
    else:
        filter = ""
    cmd = f"{tshark} -r {filename} {filter}  -T json > " + outfile
    print(cmd)
    out, err = sb.Popen(cmd, shell=True, stdout=sb.PIPE, stderr=sb.PIPE).communicate()
    if out:
        print(out)
    if err:
        print(err)
    return os.path.join(".", outfile)


def get_from_cap_file(filename, wireshark_filter=None, tshark_path=""):
    """
    Read a tethereal/tshark/wireshark file and return all the messages as a list of strings
    Requires tshark installed.

    :param filename:  the name of file (pcapng content)
    :param tshark_path: the location of tshark.
    :param wireshark_filter: apply a wireshark filter to the output
    :return: a list of messages as a list of strings
    """
    j_output = open_cap_file(filename, tshark_path, wireshark_filter)
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
            this_msg = assemble_message_from_json(j_msg, appl="sip")
            result.append(this_msg)
        except KeyError:
            continue
    return result


def assemble_message_from_json(j_msg, appl):
    if appl == "sip":
        this_msg = ""

        if "sip.Request-Line" in j_msg["_source"]["layers"]["sip"].keys():
            this_msg += j_msg["_source"]["layers"]["sip"]["sip.Request-Line"]

        elif "sip.Status-Line" in j_msg["_source"]["layers"]["sip"].keys():
            this_msg += j_msg["_source"]["layers"]["sip"]["sip.Status-Line"]

        this_msg += '\r\n'
        # this seems to include the body as well, at least in trace with notify messages with xml bodies
        this_msg += j_msg["_source"]["layers"]["sip"]["sip.msg_hdr"]

    elif appl == "http":
        for key in j_msg["_source"]["layers"]["http"]:
            if "HTTP/" in key:
                request_uri = key
        this_msg = request_uri

        if "http.request.line" in j_msg["_source"]["layers"]["http"][request_uri]:
            for line in j_msg["_source"]["layers"]["http"][request_uri]["http.request.line"]:
                this_msg += line
        else:
            for line in j_msg["_source"]["layers"]["http"][request_uri]["http.response.line"]:
                this_msg += line
        this_msg += '\r\n'
        # this seems to include the body as well, at least in trace with notify messages with xml bodies
        this_msg += j_msg["_source"]["layers"]["http"][request_uri]["http.file_data"]

    elif appl == "rtp":
        this_msg = "RTP payload"
    else:
        this_msg = appl + " content"

    return this_msg


def make_sip_message_template(sip_message, purpose="diff"):
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
    replacements = replacement_set[purpose]
    result = ""
    for line in contents.split("\r\n"):
        for item in replacements:
            patrn, rplmnt = item, replacements[item]
            line = re.sub(patrn, rplmnt, line, re.IGNORECASE)
        result += line + "\r\n"
    return result + "\r\n"


def get_msg_list_from_file(trace_file, input_format, wireshark_filter=None, tshark_path=""):
    if not tshark_path and platform.system() == "Windows":
        tshark_path = r"C:\Program Files\Wireshark"
    if input_format == "pcapng":
        list1 = get_from_cap_file(filename=trace_file, tshark_path=tshark_path, wireshark_filter=wireshark_filter)
    elif input_format == "json":
        list1 = get_sip_from_json_file(filename=trace_file)
    else:
        print("Invalid input file type: {}. Supported formats are pcapng and json".format(input_format))
        return None
    return list1


def diff(ref_trace, check_trace, input_format="pcapng", tshark_path="", filters={}):
    """
    Diff two pcapng or json files containing network captured data

    :param ref_trace: The first file. Considered as reference.
    :param check_trace: The second file. Checked to contain the same flow as the first file.
    :param input_format: Type of files to be checked. Can be "pcapng"  (default) or "json"
    :param tshark_path: Needed in case the input type is "pcapng" so that the files can be converted to json format
    :param filters: A list of filters to remove noise from messages.
    :return: The result of a list of checks
    """
    list1 = iter(get_msg_list_from_file(trace_file=ref_trace, tshark_path=tshark_path, input_format=input_format))
    list2 = iter(get_msg_list_from_file(trace_file=check_trace, tshark_path=tshark_path, input_format=input_format))
    if list1 is None or list2 is None:
        return None
    count = 0
    if "Call-ID" not in filters:
        filters["Call-ID"] = []
    for msg in list2:
        sip_msg = buildMessage(msg, {})
        if msg_filter(sip_msg, filters) is None:
            if sip_msg.type == "Request":
                filters["Call-ID"].append(sip_msg["Call-ID"])
            continue
        ref_msg = next(list1)
        ref_sip_msg = buildMessage(ref_msg, {})
        while msg_filter(ref_sip_msg, filters) is None:
            if ref_sip_msg.type == "Request":
                filters["Call-ID"].append(ref_sip_msg["Call-ID"])
            ref_msg = next(list1)
            ref_sip_msg = buildMessage(ref_msg, {})

        ref_msg_template = make_sip_message_template(ref_msg)
        msg_template = make_sip_message_template(msg)
        if msg != ref_msg:
            print("{:-^60}".format(" Difference found in message #{} ".format(count)))
            print("{:#^60}".format(" Reference message "))
            print(ref_msg)
            print("{:#^60}".format(" Matched message "))
            print(msg)

            print("{:#^60}".format(" Diff analysis "))
            d = Differ()
            for line in d.compare(ref_msg_template.splitlines(keepends=True),
                                  msg_template.splitlines(keepends=True)):
                print(line.strip())
            return False
        count += 1
    return True


def msg_filter(message, filter_data):
    """
    Used to filter a list of message based on given criteria

    :param message: A message (currently supported only sip)
    :param filter_data: A dictionary of lists with the filter data.
                        We can filter based on type of message, Call-ID header, or text found anywhere in the message.
        filter_data example:
        {"Message": ["NOTIFY", "100 Trying", "180"],
        "Call-ID": ["232ttwegwgweweggweg", "gqqh1h542h245h2", "2325235UIGBIU2390Hh45"],
        "Text": ["10.2.10.3", "302118814445", "Line10000", "keyset-info"]}
    :return: None if message matches the criteria, the message itself if it doesn't match
    """
    for excl_type in filter_data:
        if excl_type == "Message":
            for msg_type in filter_data["Message"]:
                if msg_type in message.get_status_or_method():
                    return None
        elif excl_type == "Text":
            for text in filter_data["Text"]:
                if text in message.contents():
                    return None
        elif excl_type == "Call-ID":
            for callID in filter_data["Call-ID"]:
                if message["Call-ID"] == callID:
                    return None
    return message


def check_in_trace(*conditions_list, check_trace, input_format="pcapng", tshark_path=""):
    """
    Look in the given trace file for a Message that matches the given conditions
    :param conditions_list: A list of dictionaries containing the conditions that a message in the trace should match.
                        Best described by an example:
           {"Message": "INVITE",                <- Message Req URI/Status Line should contain this string (re supported)
            "Headers": {"CSeq": "INVITE",       <- Message Header CSeq must contain this string (re)
                        "Supported": "timer"},  <- Message Header Supported must contain this string (re)
            "sdp": {"any": "PMCA",              <- Message sdp body must contain this text anywhere
                    "a_line": "PMCU",           <- Message sdp body must contain this text in an (a) line (re)
                    "o_line": "IP4"}            <- Message sdp body must contain this text in an (o) line
           "xml":  {"any": "ns:recording",      <- Message xml body must contain this text anywhere
                    "label tag": "audio",       <- Message xml body must contain this text in an a "label" tag
                    "label aor attr": "911@"}   <- Message xml body must contain this text in an "aor" attribute of
                                                    a "label" tag
            }
    :param check_trace: The trace containing the network capture under test
    :param input_format: Type of files to be checked. Can be "pcapng"  (default) or "json"
    :param tshark_path: Needed in case the input type is "pcapng" so that the files can be converted to json format
    :return:
    """
    result = []
    if input_format == "list":
        msg_list = check_trace
    else:
        msg_list = get_msg_list_from_file(check_trace, input_format=input_format, tshark_path=tshark_path)
    for conditions in conditions_list:
        for msg_str in msg_list:
            try:
                if isinstance(msg_str, SipMessage):
                    msg = msg_str
                else:
                    msg = buildMessage(msg_str)
            except:
                print("Failed to parse", msg_str)
                raise
            match = True
            for check in conditions:
                if check == "Message":
                    if not re.search(conditions["Message"], msg.get_status_or_method(), re.IGNORECASE):
                        match = False
                        continue
                elif check == "Headers":
                    for header in conditions["Headers"]:
                        if header not in msg.headers:
                            match = False
                            continue
                        elif not re.search(conditions["Headers"][header], msg[header], re.IGNORECASE):
                            match = False
                            continue
                elif check == "sdp":
                    for sdpline in conditions["sdp"]:
                        if sdpline == "any":
                            if not re.search(conditions["sdp"]["any"], msg.body, re.IGNORECASE):
                                match = False
                                continue
                        elif sdpline.endswith(" line"):
                            line_type = sdpline[0]
                            if not re.search(line_type + "=.*" + conditions["sdp"][sdpline], msg.body, re.IGNORECASE):
                                match = False
                                continue

                elif check == "xml":
                    if "<?xml" not in msg.body:
                        match = False
                        continue
                    xml_part_of_body = "<?xml" + msg.body.split("<?xml")[1].split("\r\n\r\n")[0]
                    xml_body_obj = XmlBody(xml_part_of_body)
                    for xmlelement in conditions["xml"]:
                        if xmlelement == "any":
                            if not re.search(conditions["xml"]["any"], msg.body, re.IGNORECASE):
                                match = False
                                continue
                        elif xmlelement.endswith(" tag"):
                            xml_tag = xmlelement.split(" ")[0]
                            all_tags = xml_body_obj.get_all(xml_tag)
                            if not all_tags:
                                match = False
                                continue
                            elif not any(re.search(conditions["xml"][xmlelement], tag.text, re.IGNORECASE)
                                         for tag in all_tags):
                                match = False
                                continue
                        elif xmlelement.endswith(" attr"):
                            xml_tag = xmlelement.split(" ")[0]
                            xml_attr = xmlelement.split(" ")[1]
                            all_tags = xml_body_obj.get_all(xml_tag)
                            if not all_tags:
                                match = False
                                continue
                            elif not any(re.search(conditions["xml"][xmlelement], tag.get(xml_attr), re.IGNORECASE)
                                         for tag in all_tags
                                         if tag.get(xml_attr) is not None):
                                match = False
                                continue
                else:
                    print("Unsupported check", check)
                    raise

            if match:
                result.append(msg)
                break
    return result


def summarize_trace(filename, *tests, applications=("sip", "http", "rtp"), input_format="pcapng", tshark_path=None,
                    tshark_filter=None):
    if not tshark_path and platform.system() == "Windows":
        tshark_path = r"C:\Program Files\Wireshark"
    if input_format == "json":
        with open(filename, "rb") as j_file:
            j_obj = json.load(j_file)
    elif input_format == "pcapng":
        with open(open_cap_file(filename, tshark_path, tshark_filter), "rb") as j_file:
            j_obj = json.load(j_file)
    else:
        print("Invalid input file type: {}. Supported formats are pcapng and json".format(input_format))
        return None
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
                src_addr = "{:<15}:{:>5}".format(j_msg["_source"]["layers"][ip_layer][ip_layer + ".src"],
                                                 j_msg["_source"]["layers"][transport_layer][
                                                     transport_layer + ".srcport"])
                dst_addr = "{:<15}:{:>5}".format(j_msg["_source"]["layers"][ip_layer][ip_layer + ".dst"],
                                                 j_msg["_source"]["layers"][transport_layer][
                                                     transport_layer + ".dstport"])
                if tests and application == "sip":
                    try:
                        msg_raw = assemble_message_from_json(j_msg, appl=application)
                        msg_obj = buildMessage(msg_raw)
                        msg = check_in_trace(*tests, check_trace=[msg_obj], input_format="list")
                        time_epoch = j_msg["_source"]["layers"]["frame"]["frame.time_epoch"]
                        if not msg:
                            expand = False
                        else:
                            expand = True
                        result[application].setdefault("{}:{}".format(ip_layer, transport_layer), []) \
                            .append((time_epoch, src_addr, dst_addr, msg_obj, expand))
                    except KeyError:
                        print("Unable to parse:")
                        pprint(j_msg)
                # result[application]["stream_count"] = len(result[application][ip_layer+":"+transport_layer])
                result[application]["count"] += 1

    return result
