import re


def parse_csv(csv_path):
    sections = {}
    section = ""
    with open(csv_path) as csv_file:
        for line in csv_file:
            clean_line = line.strip()
            regex_result = re.search("\[(.*)\]", line)

            if regex_result:
                section = regex_result.group(1)
                sections[section] = []
            elif clean_line and section:
                sections[section].append(clean_line)
    # TODO restore logging
    # for section in sections:
    #    info("{} : {}".format(section, str(sections[section])))
    assert sections, "Failed to parse csv file"
    return sections


#TODO refactor redundant functions
def get_subs(csv_path):
    csv_dict = parse_csv(csv_path)
    sub_lines = [x.split(",") for x in csv_dict["NUMBER"]]
    ports = dict((i[0], int(i[4])) for i in sub_lines)
    dn = dict((i[0], i[2]) for i in sub_lines)
    return dn, ports


def get_reg_subs(csv_path):
    csv_dict = parse_csv(csv_path)
    sub_lines = [x.split(",") for x in csv_dict["NUMBER"]]
    dn = dict((i[0], i[2]) for i in sub_lines if i[6].strip() == "yes")
    return dn


def get_number_of_endpoints(csv_path):
    return len(get_subs(csv_path)[0])
