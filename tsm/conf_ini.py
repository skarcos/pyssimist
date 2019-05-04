import re


def get_from_conf_ini(key: str, conf_ini_path):
    with open(conf_ini_path) as config_ini:
        contents = config_ini.read()
    return re.search("{}=(.*)".format(key), contents).group(1)


def get_OSV_sig_IP(conf_ini_path):
    # "Get OSV IP from conf.ini"
    return get_from_conf_ini("HiPathSignallingNode0Address", conf_ini_path)


def get_local_ip(conf_ini_path):
    # "Get local IP from conf.ini"
    return get_from_conf_ini("LocalIpAddress", conf_ini_path)
