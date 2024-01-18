import os
import pprint
import re

from sip.SipParser import buildMessage
from csta.CstaParser import buildMessage as buildMessageCSTA

from common.tc_logging import info
from sip import SipParser
from tshark_tools.lib import pcap2asc


def parse_asc(asc):
    order = []
    message = ""
    with open(asc) as asc_file:
        for line in asc_file:
            clean_line = line.strip()
            if line.strip("#").startswith("UCE"):
                continue
            if clean_line == '{' and message:
                order.append(asc2dict(message))
                message = line
            else:
                message += line

    last_message = asc2dict(message)
    if last_message:
        order.append(last_message)
    return order


def asc2dict(strmsg, strindx=0):
    global i
    i = strindx
    N = len(strmsg)
    buf = ''
    key = None
    strcontext = False
    d = {}
    # Just in case there is no }
    while i < N:
        s = strmsg[i]
        i += 1
        if ((not s or s.isspace()) and not strcontext) or s == "{" and not d:
            continue
        # don't recurse if we are on the start of the string
        elif s == "{" and d and not strcontext:
            buf = asc2dict(strmsg, strindx=i)
        elif s == "=" and not strcontext:
            i += 1
            key = buf
            buf = ""
        elif s == "'":
            strcontext = not strcontext
        elif s == "," and not strcontext:
            d[key] = buf
            buf = ""
        elif s == "}" and not strcontext:
            if key is not None and key not in d:
                d[key] = buf
            return d
        else:
            buf += s


def parse_csv(csv):
    # cwd = os.getcwd()
    # os.chdir(path)
    # csv = [x for x in os.listdir(".") if x[-3:] == "csv"][0]
    sections = {}
    section = ""
    with open(csv) as csv_file:
        for line in csv_file:
            clean_line = line.strip()
            M = re.search("\[(.*)\]", line)

            if M:
                section = M.group(1)
                sections[section] = []
            elif clean_line and section:
                sections[section].append(clean_line)
    # os.chdir(cwd)
    for section in sections:
        info("{} : {}".format(section, str(sections[section])))
    assert sections, "Failed to parse csv file"
    return sections


def get_new_attributes(csv_dict):
    min_dial_ext_len = 3
    # choose a list because order of replacements matters
    replacements = []
    for t in ("udp", "UDP", "tcp", "TCP", "tls", "TLS"):
        for s in "transport=", "SIP/2.0/":
            replacements.append((s + t, s + "{transport}"))
        # replacements[0-11]
    for line in csv_dict["COMMON"]:
        key, value = (x.strip() for x in line.split("="))
        if key == "HiPathSignallingIPAddress":
            osv_trace_ip = value
            replacements.append((osv_trace_ip, "{dest_ip}"))
        # replacements[12]

    sub_dict = dict()
    for line in csv_dict["NUMBER"]:
        list_line = line.split(",")
        sub_name = list_line[0]
        sub_dict[sub_name] = dict()
        sub_dict[sub_name]["trace_dn"] = list_line[1]
        sub_dict[sub_name]["test_dn"] = list_line[2]
        sub_dict[sub_name]["trace_port"] = list_line[3]
        sub_dict[sub_name]["test_port"] = list_line[4]
        sub_dict[sub_name]["trace_ip"] = list_line[5]
        sub_dict[sub_name]["reg_boolean"] = list_line[6]
        sub_dict[sub_name]["endpoint_name"] = ""
        if len(list_line) > 7:
            sub_dict["sub_name"]["reg_boolean"] = list_line[7]

    keyset_lines = dict()
    if "KEYSET" in csv_dict:
        # if True:
        for line in csv_dict["KEYSET"]:
            primary_sub, keyset_type, appearances = line.split(",", maxsplit=2)
            keyset_lines[primary_sub] = []
            for secondary_name in appearances.split(",")[1:]:
                secondary_sub = None
                for line in csv_dict["NUMBER"]:
                    sub_name, trace_dn, test_dn, trace_port, test_port, trace_ip, reg_boolean = line.split(",")
                    if sub_name == secondary_name:
                        secondary_sub = (trace_dn, test_dn)
                if secondary_sub:
                    keyset_lines[primary_sub].append(secondary_sub)
                else:
                    raise Exception("Csv misconfiguration: SUB referenced in Keyset section but not in NUMBER section")

    for sub_name in sub_dict:
        # This complicated block is because we have to somehow match NOTIFY Call-IDs to
        # Call-ID of initial subscribes. We have replaced all trace NOTIFY's Call-IDs with a
        # placeholder that contains the trace_dn and the trace port and ip.
        # Here we are trying to replace all trace numbers @ ip : port combinations with
        # the corresponding test number @ primary number  replacements.
        # This will be made use of in Subscribe() function to save SUBSCRIBE Call-IDs to
        # corresponding number @ primary number combination.
        #  ---  notify troubles start
        replacements.append(("subscription_{}@{}:{}_Call-ID".format(sub_dict[sub_name]["trace_dn"],
                                                                    sub_dict[sub_name]["trace_ip"],
                                                                    sub_dict[sub_name]["trace_port"]),
                             "subscription_{0}@{0}_Call-ID".format(sub_dict[sub_name]["test_dn"])))
        replacements.append(("subscription_{}@{}:{}_to_tag".format(sub_dict[sub_name]["trace_dn"],
                                                                   sub_dict[sub_name]["trace_ip"],
                                                                   sub_dict[sub_name]["trace_port"]),
                             "subscription_{0}@{0}_to_tag".format(sub_dict[sub_name]["test_dn"])))
        if "KEYSET" in csv_dict:
            # if True:
            for secondary_dn in keyset_lines[sub_name]:
                replacements.append(("subscription_{}@{}:{}_Call-ID".format(secondary_dn[0],
                                                                            sub_dict[sub_name]["trace_ip"],
                                                                            sub_dict[sub_name]["trace_port"]),
                                     "subscription_{}@{}_Call-ID".format(secondary_dn[1],
                                                                         sub_dict[sub_name]["test_dn"])))
                replacements.append(("subscription_{}@{}:{}_to_tag".format(secondary_dn[0],
                                                                           sub_dict[sub_name]["trace_ip"],
                                                                           sub_dict[sub_name]["trace_port"]),
                                     "subscription_{}@{}_to_tag".format(secondary_dn[1],
                                                                        sub_dict[sub_name]["test_dn"])))
        #  ---  notify troubles end

    # Make two separate loops so that the replacement order is correct
    for sub_name in sub_dict:
        replacements.append((sub_dict[sub_name]["trace_dn"], "{%s}" % sub_name))
        replacements.append(("{}:{}".format(sub_dict[sub_name]["trace_ip"], sub_dict[sub_name]["trace_port"]),
                             "{}:{}".format("{local_ip}", "{%s_port}" % sub_name)))
    for sub_name in sub_dict:
        # Do this once for each replacement so that first all ip:port are replaced and then all ip are replaced
        replacements.append((sub_dict[sub_name]["trace_ip"], "{local_ip}"))  # test_ip
        # TODO: verify what TSM does with partial matches - DN extensions
        for i in range(len(sub_dict[sub_name]["trace_dn"]), min_dial_ext_len - 1, -1):
            trace_dial_extension = "sip:%s@" % sub_dict[sub_name]["trace_dn"][-i:]
            test_dial_extension = "sip:{%s_ext%d}@" % (sub_name, i)
            replacements.append((trace_dial_extension, test_dial_extension))
            trace_dial_extension2 = "Line%s" % sub_dict[sub_name]["trace_dn"][-i:]
            test_dial_extension2 = "Line{%s_ext%d}" % (sub_name, i)
            replacements.append((trace_dial_extension2, test_dial_extension2))
            trace_dial_extension3 = "%s@" % sub_dict[sub_name]["trace_dn"][-i:]
            test_dial_extension3 = "{%s_ext%d}@" % (sub_name, i)
            replacements.append((trace_dial_extension3, test_dial_extension3))

    return replacements


def replace_trace_data(replacements, trace_message):
    """Replace trace ip, ports and dns with test values"""
    for item in replacements:
        trace_message = trace_message.replace(item[0], item[1])
    return trace_message


def categorize_pcap_msgs(messages, osv_ip):
    """
    Adds required 'type' in messages in case they were captured by wireshark
    See also tshark_tools.lib.psap2asc
    TODO: Add CSTA handling
    """
    for message in messages:
        if message["type"] == "_SIP_":
            if message["data"]["sender"].split(":")[0].strip() == osv_ip:
                message["data"]["sender"] = "ttudProc1"
                message["type"] = "OP_RTT_RT_SIP_OG"
            elif message["data"]["receiver"].split(":")[0].strip() == osv_ip:
                message["data"]["receiver"] = "ttudProc1"
                message["type"] = "OP_RTT_RT_SIP_IC"


def actual(list_of_messages):
    """
    :param list_of_messages: A list of messages found in an asc file
    :return: A list containing only the subset of these messages that
             we are interested in (eg only SIP and CSTA messages)
    """
    actual_messages = []
    dialogs = set()
    for messg in list_of_messages:
        # TODO : verify these rules
        try:
            if "_SIP_" in messg["type"]:
                m = buildMessage(messg["data"]["sip_msg"], {})
            else:
                m = buildMessageCSTA(messg["data"]["csta_msg"]["data"], {}, 0)
        except (TypeError, KeyError):
            # It is not a sip/csta message and ["data"] returns a string
            continue
        if messg["type"] == "OP_RTT_RT_SIP_IC":
            if m.get_status_or_method() == "REGISTER":
                # Ignore registrations caught in asc file
                continue
            # elif m.get_status_or_method() == "NOTIFY":
            #     # Add a placeholder to apply the Call-ID from Notify
            #     # The replacement for this placeholder is set in Subscribe()
            #     # First we are also replacing trace ip and port with test DN in get_new_attributes()
            #     user = re.match("^NOTIFY sip:(.*)@.*$", m.request_line).group(1)
            #     trace_address = messg["data"]["sender"]
            #     call_id_placeholder = "subscription_%s@%s_Call-ID" % (user, trace_address)
            #     to_tag_placeholder = "subscription_%s@%s_to_tag" % (user, trace_address)
            #     #                from_tag_placeholder = "{subscription_%s@%s_from_tag}" % (user, trace_address)
            #
            #     messg["data"]["sip_msg"] = re.sub("Call-ID: .*",
            #                                       "Call-ID: {%s}" % call_id_placeholder,
            #                                       messg["data"]["sip_msg"])
            #     #                message["data"]["sip_msg"] = re.sub(r"From: (.*);tag=[^;\s]+(.*)",
            #     #                                                    r"From: \1;tag={}\2".format(from_tag_placeholder),
            #     #                                                    message["data"]["sip_msg"])
            #     messg["data"]["sip_msg"] = re.sub(r"To: (.*);tag=[^;\s]+(.*)",
            #                                       r"To: \1;tag={%s}\2" % to_tag_placeholder,
            #                                       messg["data"]["sip_msg"])
            if m.type == "Response" and m["Call-ID"] not in dialogs:
                continue
            dialogs.add(m["Call-ID"])
            actual_messages.append(messg)
        elif messg["type"] == "OP_RTT_RT_SIP_OG":
            if m.type == "Response" and m["Call-ID"] not in dialogs:
                continue
            # if m.get_status_or_method() == "NOTIFY" and m["Call-ID"] not in dialogs:  #  TODO: keep only event uaCSTA,  or Content type application/csta...
            #     continue
            dialogs.add(m["Call-ID"])
            actual_messages.append(messg)
        elif messg["type"] == "OP_RTT_RT_CSTA_IC":
            actual_messages.append(messg)
        elif messg["type"] == "OP_RTT_RT_CSTA_OG":
            actual_messages.append(messg)
        else:
            continue
    return actual_messages


class SipContext:
    def __init__(self, sub_name):
        self.test_call_id_of_trace_call_id = {}
        self.test_branch_of_trace_branch = {}
        self.dialog_elements_of_call_id = {}
        self.known_transactions = {}
        self.known_dialogs = {}
        self.sub_name = sub_name
        self.current_transaction = None
        self.current_dialog = None

    def out(self, msg):
        """
        Send a sip message in the current sip context
        :param msg: A string containing the sip message as found in the traces
        :return: (True/False if the msg creates a new dialog, the request or status code of msg)
        """
        m = SipParser.buildMessage(msg)
        is_new = True
        trace_branch = m.via_branch
        trace_call_id = m["Call-ID"]
        existing_call_id_list = self.test_call_id_of_trace_call_id.keys()
        # Check if we are sending a response or a request in the same dialog
        if trace_call_id in existing_call_id_list:
            is_new = False
            test_call_id = self.test_call_id_of_trace_call_id[trace_call_id]
            m["Call-ID"] = test_call_id
            if m.via_branch in self.test_branch_of_trace_branch:
                m.via_branch = self.test_branch_of_trace_branch[trace_branch]
            if m.type == "Request":
                m.to_tag = self.dialog_elements_of_call_id[test_call_id]["remote_tag"]
                m.from_tag = self.dialog_elements_of_call_id[test_call_id]["my_tag"]
            else:
                m.to_tag = self.dialog_elements_of_call_id[test_call_id]["my_tag"]
                m.from_tag = self.dialog_elements_of_call_id[test_call_id]["remote_tag"]

        info(self.sub_name + " sends %s" % m.get_status_or_method())
        test_call_id = m["Call-ID"]
        self.test_call_id_of_trace_call_id[trace_call_id] = test_call_id
        if m.type == "Request":
            self.dialog_elements_of_call_id[test_call_id] = dict([("my_tag", m.to_tag),
                                                                  ("remote_tag", m.from_tag)])
        else:
            self.dialog_elements_of_call_id[test_call_id] = dict([("my_tag", m.from_tag),
                                                                  ("remote_tag", m.to_tag)])
            is_new = False
        self.test_branch_of_trace_branch[trace_branch] = m.via_branch
        return is_new, m.get_status_or_method(), m.type, m.get_dialog()

    def get_known_transaction(self, msg):
        """
        Matches a msg to an existing transaction
        :param msg: A string containing the sip message as found in the traces
        :return: If the message is for a previous transaction, the variable name that corresponds to that transaction,
                    else None
        """
        m = SipParser.buildMessage(msg)
        trace_msg_transaction = m.get_transaction()

        if trace_msg_transaction not in self.known_transactions.values():
            return None, trace_msg_transaction
        else:
            for key in self.known_transactions:
                if self.known_transactions[key] == trace_msg_transaction:
                    return key, trace_msg_transaction
            return "Generate-ERROR-SipContext-Transactions", trace_msg_transaction

    def get_message_from_dialog(self, dialog):
        """
        Gets the message variable corresponding to the known dialogs dictionary
        :param dialog: The requested dialog
        :return: If the dialog is known the variable name that corresponds to that transaction, else None
        """
        for d in self.known_dialogs:
            if self.known_dialogs[d] == dialog:
                return d
        return None



def generate(messages, tracefile):
    """
    Generate a script to run in a TSM testsuite.
    The test is written in a file named "test.py"

    :param messages: A list of messages in the correct order
    :return: None
    """
    top = '''\
try: 
    from tc_data import tc_message
except:
    pass
from common.util import LoadThread
from threading import Event
from time import sleep

'''
    sip_main = "def sip_flow(): # main sip function name must be sip_flow\n"
    csta_main = "def csta_flow(): # main csta function name must be csta_flow\n"

    tc_messages = {}
    csv_filename = tracefile.rsplit(".", maxsplit=1)[0] + ".csv"
    csv_dict = parse_csv(csv_filename)
    replacements = get_new_attributes(csv_dict)
    address_to_sub = {}
    dn_to_sub = {"None": None}
    sub_flows = {}
    sub_csta_flows = {None: "def CSTA_app_flow():\n"}
    invoke_ids = {}
    xref_id_to_sub = {}
    for line in csv_dict["NUMBER"]:
        # sub_name, trace_dn, test_dn, trace_port, test_port, trace_ip, reg_boolean = line.split(",") #for 7 values
        list_line = line.split(",")
        print("reg_boolean:", list_line[6])
        sub_name, trace_dn, test_dn, trace_port, test_port, trace_ip, reg_boolean = list_line[:7]
        if len(list_line) > 7:
            endpoint_name = list_line[7]
            print("endpoint_name:", list_line[7])

        address_to_sub["{}:{}".format(trace_ip, trace_port)] = sub_name
        dn_to_sub[trace_dn] = sub_name
        sub_flows[sub_name] = "def %s_flow():\n" % sub_name
        sub_csta_flows[sub_name] = "def %s_csta_flow():\n" % sub_name

    csta_main += "    csta_app_thread = LoadThread(target=CSTA_app_flow, daemon=True)\n"
    csta_main += "    csta_app_thread.start()\n"

    for sub in sub_flows:
        sip_main += "    {0}_thread = LoadThread(target={0}_flow, daemon=True)\n".format(sub)
        csta_main += "    {0}_csta_thread = LoadThread(target={0}_csta_flow, daemon=True)\n".format(sub)
    for sub in sub_flows:
        sip_main += "    {0}_thread.start()\n".format(sub)
        csta_main += "    {0}_csta_thread.start()\n".format(sub)
    for sub in sub_flows:
        sip_main += "    {0}_thread.join()\n".format(sub)
        csta_main += "    {0}_csta_thread.join()\n".format(sub)

    csta_main += "    csta_app_thread.join()\n"

    with open("test_flow.py", "w") as F:
        dialogs = {}
        for sub in sub_flows:
            dialogs[sub] = SipContext(sub)

        count = 0
        sync_wait = ""
        sync_set = ""
        osv_trace_ip = replacements[12][0]
        categorize_pcap_msgs(messages, osv_trace_ip)
        for _message in actual(messages):
            count += 1
            try:

                if "_SIP_" in _message["type"]:
                    address = _message["data"]["receiver"]
                    if address.startswith("ttud"):
                        address = _message["data"]["sender"]
                    try:
                        sub = address_to_sub[address]
                    except KeyError:
                        # Ignored messages, captured in trace and related to subscribers not declared in csv
                        continue
                    tc_message_str = _message["data"]["sip_msg"]
                    sub_context = dialogs[sub]
                    new_id, status_or_method, message_type, this_dialog = sub_context.out(tc_message_str)
                    other_message_var = sub_context.get_message_from_dialog(this_dialog)
                    tc_message_var, this_transaction = sub_context.get_known_transaction(tc_message_str)

                    tc_message_name = status_or_method + " #" + str(count)
                    if message_type == "Request":
                        # create a sync point
                        sync_name = "sync_{}".format(tc_message_name.replace(" #", "_"))
                        top += sync_name + " = Event()\n"
                        sync_set = '    ' + sync_name + ".set()\n"
                        sync_wait = '    ' + sync_name + ".wait(60)\n"

                    if _message["type"] == "OP_RTT_RT_SIP_IC":

                        transaction_found = True
                        if tc_message_var is None:
                            transaction_found = False
                            tc_message_var = "m_" + re.sub("[ #]", "_", tc_message_name)
                            sub_context.known_transactions[tc_message_var] = this_transaction
                            sub_context.known_dialogs[tc_message_var] = this_dialog
                        if new_id:
                            block = '\n    {msgv} = {sender}.send_new(message_string=tc_message["{msg}"])\n'.format(
                                msgv=tc_message_var,  # INVITE__11
                                msg=tc_message_name,  # INVITE #11
                                sender=sub)
                        elif this_transaction != sub_context.current_transaction and \
                                sub_context.current_transaction is not None \
                                and transaction_found:
                            sub_context.known_transactions[tc_message_var] = this_transaction
                            block = '    {sender}.reply_to({msgv}, tc_message["{msg}"])\n'.format(
                                msgv=tc_message_var,
                                msg=tc_message_name,
                                sender=sub)
                        elif sub_context.current_dialog["Call-ID"] != this_dialog[
                            "Call-ID"] and other_message_var is not None:
                            block = '    {sender}.send(tc_message["{msg}"], dialog={msgv}.get_dialog())\n'.format(
                                msg=tc_message_name,
                                sender=sub,
                                msgv=other_message_var)
                        else:
                            block = '    {sender}.send(tc_message["{msg}"])\n'.format(msg=tc_message_name,
                                                                                      sender=sub)

                        sub_flows[sub] += block

                        tc_messages[tc_message_name] = replace_trace_data(replacements,
                                                                          re.sub("\n[ \t]*", "\n", tc_message_str))
                        sub_context.current_transaction = this_transaction
                        sub_context.current_dialog = this_dialog
                    elif _message["type"] == "OP_RTT_RT_SIP_OG":

                        # we add the incoming messages in the tc_data list although we don't actually use the whole
                        # message in the script. Just in case, we will also remove the dynamic elements from the
                        # message
                        tc_messages[tc_message_name] = replace_trace_data(replacements,
                                                                          re.sub("\n[ \t]*", "\n", tc_message_str))
                        if sub_context.current_dialog and \
                                sub_context.current_dialog["Call-ID"] != this_dialog["Call-ID"] \
                                and other_message_var is not None:
                            in_dialog = ", dialog={msgv}.get_dialog()".format(msgv=other_message_var)
                        else:
                            in_dialog = ""

                        if tc_message_var is None:
                            tc_message_var = "m_" + re.sub("[ #]", "_", tc_message_name)
                            sub_context.known_transactions[tc_message_var] = this_transaction
                            sub_context.known_dialogs[tc_message_var] = this_dialog
                            block = '\n    {msgv} = {sender}.wait_for_message("{msg}"{dialog})\n'.format(
                                msgv=tc_message_var,
                                msg=status_or_method,
                                sender=sub,
                                dialog=in_dialog)
                        else:
                            # wait_for_message expects the request uri or status code as input, not the whole message
                            block = '    {sender}.wait_for_message("{msg}"{dialog})\n'.format(msg=status_or_method,
                                                                                              sender=sub,
                                                                                              dialog=in_dialog)
                        sub_flows[sub] += block
                        sub_context.current_transaction = this_transaction
                        sub_context.current_dialog = this_dialog
                    for _sub in sub_flows:
                        if _sub == sub:
                            if sync_set not in sub_flows[str(_sub)] and sync_wait not in sub_flows[str(_sub)]:
                                sub_flows[_sub] += sync_set
                        else:
                            if sync_wait not in sub_flows[str(_sub)] and sync_set not in sub_flows[str(_sub)]:
                                sub_flows[_sub] += sync_wait

                elif "_CSTA_" in _message["type"]:
                    tc_message_str = _message["data"]["csta_msg"]["data"]
                    tc_message = buildMessageCSTA(tc_message_str, {}, 0)
                    tc_message_name = tc_message.event + " #" + str(count)
                    sub = None
                    if tc_message.is_request():
                        # TODO: fix this terrible hack to match deviceID to sub.
                        #  might not be fixable until we parse the CSTA TRACE DEVICE csv section
                        #  to get csta device information
                        d_id = None
                        if d_id is None:
                            d_id = tc_message["deviceID"]
                        if d_id is None:
                            d_id = tc_message["deviceObject"]
                        if d_id is None:
                            d_id = tc_message["callingDevice"]
                        # get the first DN from csv that is substring of the device id found in the message
                        d_id_csv_match = list(filter(lambda s: str(d_id).endswith(s), dn_to_sub))[0]
                        sub = dn_to_sub[d_id_csv_match]
                        invoke_id = _message["data"]["csta_msg"]["Invoke_ID"]
                        invoke_ids.setdefault(sub, []).append(invoke_id)

                        if tc_message.event in ("SystemRegister", "SystemStatus", "MonitorStart", "RequestSystemStatus"):
                            continue
                        else:
                            # create a sync point
                            sync_name = "sync_{}".format(tc_message_name.replace(" #", "_"))
                            top += sync_name + "= Event()\n"
                            sync_set = '    ' + sync_name + ".set()\n"
                            sync_wait = '    ' + sync_name + ".wait(60)\n"

                    elif tc_message.is_response():
                        # determine the corresponding user by the invoke id of the response
                        invoke_id = _message["data"]["csta_msg"]["Invoke_ID"]
                        request_found = False
                        for s in invoke_ids:
                            if s is not None and invoke_id in invoke_ids[s]:
                                sub = s
                                request_found = True
                                break
                        if tc_message.event == "MonitorStartResponse":
                            xref_id = tc_message["monitorCrossRefID"]
                            xref_id_to_sub[xref_id] = sub
                            continue
                        if not request_found:
                            # discard response caught in trace if corresponding request was not caught
                            continue
                    elif tc_message.is_event():
                        # we must determine the recipient based on the xref_id of the event
                        xref_id = tc_message["monitorCrossRefID"]
                        if xref_id in xref_id_to_sub:
                            sub = xref_id_to_sub[xref_id]

                    if _message["type"] == "OP_RTT_RT_CSTA_IC":
                        # incoming (outgoing for client/test) csta messages are either events or responses
                        block = '    {sender}_csta.send(message=tc_message["{msg}"])\n'.format(msg=tc_message_name,
                                                                                               sender=sub)
                        block += sync_set
                    elif _message["type"] == "OP_RTT_RT_CSTA_OG":
                        if sub and sync_wait not in sub_csta_flows[str(sub)] and sync_set not in sub_csta_flows[
                            str(sub)]:
                            block = sync_wait
                        else:
                            block = ''
                        # outgoing (incoming for client/test) csta messages are either requests or responses
                        block += '    {sender}_csta.wait_for_message(message="{msg}")\n'.format(msg=tc_message.event,
                                                                                                sender=sub)

                    block = block.replace("None_csta.wait_for_message(", "CSTA.wait_for_csta_message(for_user=None,")
                    block = block.replace("None_csta.send(", "CSTA.send(from_user=None,")

                    if sub is None:
                        sub_csta_flows[None] += block
                    else:
                        sub_csta_flows[str(sub)] += block
                    tc_messages[tc_message_name] = replace_trace_data(replacements, tc_message_str)
            except:
                print(_message)
                raise

        F.write(top + "\n")
        F.write(sip_main)

        for sub in sub_flows:
            F.write("\n" + sub_flows[sub] + "\n")
            if sub_flows[sub][-2:] == ":\n":
                F.write("    pass\n")

        if sub_csta_flows:
            F.write("\n" + csta_main)
            for sub in sub_csta_flows:
                F.write("\n" + sub_csta_flows[sub])
                if sub_csta_flows[sub][-2:] == ":\n":
                    F.write("    pass\n")

    with open("tc_data.py", "w") as tc_data_f:
        tc_data_f.write("tc_message=" + pprint.pformat(tc_messages, width=300))


if __name__ == "__main__":
    # ascfile = os.path.join("..", "ignore\\UNSPsip_cpu_subscriptions\\UNSPsip_cpu_subscriprions.asc")
    # messages = parse_asc(ascfile)
    tsharkfile = ".\\simclientsip_side.pcapng"
    messages = pcap2asc(tsharkfile, applications=("sip",), keep_temp_files=True)
    os.chdir(os.path.dirname(tsharkfile))
    generate(messages, tsharkfile)
