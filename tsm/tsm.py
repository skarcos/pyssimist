import os, sys
sys.path.append(os.path.join(os.getcwd(), "..", "..", "..", "..", "Tools", "pyssimist"))
sys.path.append(os.getcwd())
import common.util as util
from common import client
import csv
import conf_ini
import utilities.logger.logger_utilities as logger_utilities
from sip.SipEndpoint import SipEndpoint
import test_flow


def get_test_case_name(test_case_path):
    return os.path.basename(os.path.abspath(os.path.join(test_case_path, "..")))


def get_csv_path(test_case_path):
    test_case_name = get_test_case_name(test_case_path)
    csv_path = os.path.abspath(os.path.join(test_case_path, "..")) + '\\' + test_case_name + '.csv'
    return csv_path


def get_conf_ini_path(test_case_path):
    conf_ini_path = os.path.abspath(os.path.join(test_case_path, "..", "..", "..", "..", "Tools", "TestSuiteManager")) \
                    + '\conf.ini'
    return conf_ini_path


def get_test_case_log(test_case_path):
    return os.path.abspath(os.path.join(test_case_path, "..")) + '\Log\Subs.txt'


def get_logger(test_case_path):
    test_case_name = get_test_case_name(test_case_path)
    test_case_log = get_test_case_log(test_case_path)
    return logger_utilities.get_logger(test_case_name, test_case_log)


# TODO dest_port should be read from csv
def get_parameters(test_case_path):
    conf_ini_path = get_conf_ini_path(test_case_path)
    csv_path = get_csv_path(test_case_path)
    number_of_endpoints = csv.get_number_of_endpoints(csv_path)
    parameters = util.dict_2({"dest_ip": conf_ini.get_OSV_sig_IP(conf_ini_path),
                              "dest_port": 5060,
                              "transport": conf_ini.get_from_conf_ini("DefaultTransportProtocol", conf_ini_path),
                              "callId": util.randomCallID,
                              "fromTag": util.randomTag,
                              "local_ip": conf_ini.get_local_ip(conf_ini_path),
                              "number_of_endpoints": number_of_endpoints,
                              "viaBranch": util.randomBranch(),
                              "epid": lambda x=6: "SC" + util.randStr(x),
                              "expires": "360",
                              "bodyLength": "0"  # Will be updated upon send
                              })
    return parameters


def initialize_from_csv():
    csv_path = get_csv_path(os.getcwd())
    dn, ports = csv.get_subs(csv_path)
    parameters = get_parameters(os.getcwd())

    # ADDED CODE
    logger = get_logger(os.getcwd())
    global debug, info, warning, error, critical, exception
    debug, info, warning, error, critical, exception = logger.debug, logger.info, logger.warning, logger.error, \
                                                       logger.critical, logger.exception
    client.debug = debug
    sip_server_address = (parameters["dest_ip"], parameters["dest_port"])
    for sub in dn:
        exec('test_flow.{} = SipEndpoint({})'.format(sub, dn[sub]))
        exec('test_flow.{}.parameters.update(parameters)'.format(sub))
        local_address = (parameters["local_ip"], ports[sub])
        exec('test_flow.{}.connect(local_address, sip_server_address, parameters["transport"])'.format(sub))
        exec('test_flow.{}.register()'.format(sub))

def cleanup():
    csv_path = get_csv_path(os.getcwd())
    dn, ports = csv.get_subs(csv_path)
    for sub in dn:
        exec('test_flow.{}.unregister()'.format(sub))

if __name__ == "__main__":
    try:
        initialize_from_csv()
    except:
        exception("***ERROR in setup")
 
    try:
        test_flow.sip_flow()
        info("NUMBER.OF.NOT.FAILED.CALLS:1")
        info("NUMBER.OF.FAILED.CALLS:0")
        info("SUCCESSFULEXITING")
    except:
        exception("***ERROR in SIP_FLOW")

    try:
        cleanup()
    except:
        exception("***ERROR in Clean-up")
