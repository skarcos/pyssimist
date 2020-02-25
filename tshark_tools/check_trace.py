from tshark_tools.lib import get_from_cap_file
from sip.SipParser import buildMessage

L = get_from_cap_file("only_sip.pcap", tshark_path=r"c:\Program Files\Wireshark")

calls = []

for message in L:
    m = buildMessage(message, {})

    if m.get_status_or_method() == "INVITE":
        calls.append(m.header["Call-ID"])
    elif m["Call-ID"] in calls and m.type == "Response":
        assert m.status in ("200 OK", "100 Trying", "180 Ringing"), \
            "Validation error: Received:\n{}".format(m.contents())
