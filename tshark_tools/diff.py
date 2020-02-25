import re
from difflib import Differ
from pprint import pprint

from common.util import XmlBody
from sip.SipParser import buildMessage
from tshark_tools.lib import make_sip_message_template, get_msg_list_from_file, summarize_trace


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
                filters["Call-ID"].append(sip_msg.headers["Call-ID"])
            continue
        ref_msg = next(list1)
        ref_sip_msg = buildMessage(ref_msg, {})
        while msg_filter(ref_sip_msg, filters) is None:
            if ref_sip_msg.type == "Request":
                filters["Call-ID"].append(ref_sip_msg.headers["Call-ID"])
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
                if message.headers["Call-ID"] == callID:
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
    msg_list = get_msg_list_from_file(check_trace, input_format=input_format, tshark_path=tshark_path)
    for conditions in conditions_list:
        for msg_str in msg_list:
            try:
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
                        elif not re.search(conditions["Headers"][header], msg.headers[header], re.IGNORECASE):
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
                            if not re.search(line_type+"=.*"+conditions["sdp"][sdpline], msg.body, re.IGNORECASE):
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

            if match:
                print(msg)
                break
    return None


if __name__ == "__main__":
    #diff(ref_trace="reference.json", check_trace="traceoutput.json", input_format="json")
    ignore = {"Message": ["OPTIONS"]}

    #diff(ref_trace="simclientsip_side.pcapng", check_trace="bcfe.pcap", input_format="pcapng", filters=ignore)
    Test1 = {"Message": "200 OK",
             "Headers": {"CSeq": "INVITE",
                         "Supported": "timer"},
             "sdp": {"any": "PCMA",
                     "a line": "PCMU",
                     "o line": "IP4"}
             }
    Test0 = {"xml":  {"any": "ns:recording",
                      "label tag": "audio",
                      "nameID aor attr": "sip:912119@grtsep41l3n1sipsm.h8k.sec"}
             }
    #check_in_trace(Test0, Test1, check_trace="bcfe.pcap")

    ignore = {"Message": ["OPTIONS", "SUBSCRIBE"]}
    #diff(ref_trace="bcf_egress_comfort_noise_enabled.pcap", check_trace="bcf_e_selective.pcap", input_format="pcapng", filters=ignore)

    print(summarize_trace("bcf_egress_comfort_noise_enabled.pcap"))
    pprint(summarize_trace("bcf_e_selective.pcap"))
