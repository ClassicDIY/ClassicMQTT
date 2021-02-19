import socket
import logging
import sys, getopt
import os



def validateStrParameter(param, name, defaultValue, log):
    if isinstance(param, str): 
        return param
    else:
        log.error("Invalid parameter, {} passed for {}".format(param, name))
        return defaultValue


def validateHostnameParameter(param, name, defaultValue, log):
    try:
        socket.gethostbyname(param)
    except Exception as e:
        log.warning("Name resolution failed for {} passed for {}".format(param, name))
        log.exception(e, exc_info=False)
    return param


def validateIntParameter(param, name, defaultValue, log):
    try: 
        temp = int(param) 
    except Exception as e:
        log.error("Invalid parameter, {} passed for {}".format(param, name))
        log.exception(e, exc_info=False)
        return defaultValue
    return temp


# --------------------------------------------------------------------------- # 
# Handle the Client command line arguments
# --------------------------------------------------------------------------- # 
def handleClientArgs(argv,argVals):

    log = logging.getLogger('classic_mqtt_client')

    try:
      opts, args = getopt.getopt(argv,"h",
                    ["classic_name=",
                     "mqtt=",
                     "mqtt_port=",
                     "mqtt_root=",
                     "mqtt_user=",
                     "mqtt_pass=",
                     "file="])
    except getopt.GetoptError:
        print("Error parsing command line parameters, please use: py --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --file <filename>".format( \
                argVals['classicName'], argVals['mqttHost'], argVals['mqttPort'], argVals['mqttRoot'] ))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ("Parameter help: py --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --file <filename>".format( \
                    argVals['classicName'], argVals['mqttHost'], argVals['mqttPort'], argVals['mqttRoot']))
            sys.exit()
        elif opt in ('--classic_name'):
            argVals['classicName'] = validateStrParameter(arg,"classic_name", argVals['classicName'], log)
        elif opt in ("--mqtt"):
            argVals['mqttHost'] = validateHostnameParameter(arg,"mqtt",argVals['mqttHost'], log)
        elif opt in ("--mqtt_port"):
            argVals['mqttPort'] = validateIntParameter(arg,"mqtt_port", argVals['mqttPort'], log)
        elif opt in ("--mqtt_root"):
            argVals['mqttRoot'] = validateStrParameter(arg,"mqtt_root", argVals['mqttRoot'], log)
        elif opt in ("--mqtt_user"):
            argVals['mqttUser'] = validateStrParameter(arg,"mqtt_user", argVals['mqttUser'], log)
        elif opt in ("--mqtt_pass"):
            argVals['mqttPassword'] = validateStrParameter(arg,"mqtt_pass", argVals['mqttPassword'], log)
        elif opt in ("--file"):
            argVals['file'] = validateStrParameter(arg,"file", argVals['file'], log)

    argVals['classicName'] = argVals['classicName'].strip()
    argVals['mqttHost'] = argVals['mqttHost'].strip()
    argVals['mqttUser'] = argVals['mqttUser'].strip()
    argVals['file'] = argVals['file'].strip()

    log.info("classicName = {}".format(argVals['classicName']))
    log.info("mqttHost = {}".format(argVals['mqttHost']))
    log.info("mqttPort = {}".format(argVals['mqttPort']))
    log.info("mqttRoot = {}".format(argVals['mqttRoot']))
    log.info("mqttUser = {}".format(argVals['mqttUser']))
    #log.info("mqttPassword = **********")
    log.info("mqttPassword = {}".format(argVals['mqttPassword']))
    log.info("file = {}".format(argVals['file']))

    #Make sure the last character in the root is a "/"
    if (not argVals['mqttRoot'].endswith("/")):
        argVals['mqttRoot'] += "/"
   