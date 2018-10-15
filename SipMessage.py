class SipMessage(object):
    '''
    Represantation of a SIP message
    header_dict example:
        {"method": "OPTIONS",
        "sourceID": "1112223334",
        "destID": "4443332221"}
    '''
    def __init__(self,header_dict,body):
        #s_ip,s_port,d_ip,d_port
        self.header=header_dict
        self.headers=self.header
        self.body=body
        # merge both dictionaries into 1
        #self.key=self.header.update(self.body)

    def __hash__(self,key):
        return self.header[key]
            
    def __repr__(self):
        if self.type=="Request":
            first_line=self.request_line
        else:
            first_line=self.status_line
        result=first_line+"\r\n"
        result+="\r\n".join(k+": "+v for k,v in self.header.items())
        result+="\r\n"
        result+="\r\n"+self.body
        return result

    def __str__(self):
        return repr(self)

    def message(self):
        return repr(self)

if __name__=="__main__":
    pass
