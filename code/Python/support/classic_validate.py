import socket
import logging


log = logging.getLogger('classic_mqtt')

def validateStrParameter(param, name, defaultValue):
    if isinstance(param, str): 
        return param
    else:
        log.error("Invalid parameter, {} passed for {}".format(param, name))
        return defaultValue

def validateURLParameter(param, name, defaultValue):
    try:
        socket.gethostbyname(param)
        return param
    except Exception as e:
        log.error("Invalid parameter, {} passed for {}".format(param, name))
        log.exception(e, exc_info=False)
        return defaultValue

def validateIntParameter(param, name, defaultValue):
    try: 
        temp = int(param) 
    except Exception as e:
        log.error("Invalid parameter, {} passed for {}".format(param, name))
        log.exception(e, exc_info=False)
        return defaultValue
    return temp


