import socket
import logging
import sys, getopt


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


# --------------------------------------------------------------------------- # 
# Handle the command line arguments
# --------------------------------------------------------------------------- # 
def handleArgs(argv,argVals, MIN_WAKE_DURATION_SECS):

    try:
      opts, args = getopt.getopt(argv,"h",
                    ["classic=",
                     "classic_port=",
                     "classic_name=",
                     "mqtt=",
                     "mqtt_port=",
                     "mqtt_root=",
                     "mqtt_user=",
                     "mqtt_pass=",
                     "wake_publish_rate=",
                     "snooze_publish_rate=",
                     "wake_duration="])
    except getopt.GetoptError:
        print("Error parsing command line parameters, please use: py --classic <{}> --classic_port <{}> --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --wake_publish_rate <{}> --snooze_publish_rate <{}> --wake_duration <{}>".format( \
                    argVals['classicHost'], argVals['classicPort'], argVals['classicName'], argVals['mqttHost'], argVals['mqttPort'], argVals['mqttRoot'], argVals['awakePublishCycleLimit'], argVals['snoozePublishCycleLimit'], int(argVals['awakePublishLimit']*argVals['awakePublishCycleLimit'])))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ("Parameter help: py --classic <{}> --classic_port <{}> --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --wake_publish_rate <{}> --snooze_publish_rate <{}> --wake_duration <{}>".format( \
                    argVals['classicHost'], argVals['classicPort'], argVals['classicName'], argVals['mqttHost'], argVals['mqttPort'], argVals['mqttRoot'], argVals['awakePublishCycleLimit'], argVals['snoozePublishCycleLimit'], int(argVals['awakePublishLimit']*argVals['awakePublishCycleLimit'])))
            sys.exit()
        elif opt in ('--classic'):
            argVals['classicHost'] = validateURLParameter(arg,"classic",argVals['classicHost'])
        elif opt in ('--classic_port'):
            argVals['classicPort'] = validateIntParameter(arg,"classic_port", argVals['classicPort'])
        elif opt in ('--classic_name'):
            argVals['classicName'] = validateStrParameter(arg,"classic_name", argVals['classicName'])
        elif opt in ("--mqtt"):
            argVals['mqttHost'] = validateURLParameter(arg,"mqtt",argVals['mqttHost'])
        elif opt in ("--mqtt_port"):
            argVals['mqttPort'] = validateIntParameter(arg,"mqtt_port", argVals['mqttPort'])
        elif opt in ("--mqtt_root"):
            argVals['mqttRoot'] = validateStrParameter(arg,"mqtt_root", argVals['mqttRoot'])
        elif opt in ("--mqtt_user"):
            argVals['mqttUser'] = validateStrParameter(arg,"mqtt_user", argVals['mqttUser'])
        elif opt in ("--mqtt_pass"):
            argVals['mqttPassword'] = validateStrParameter(arg,"mqtt_pass", argVals['mqttPassword'])
        elif opt in ("--wake_publish_rate"):
            argVals['awakePublishCycleLimit'] = int(validateIntParameter(arg,"wake_publish_rate", argVals['awakePublishCycleLimit']))
        elif opt in ("--snooze_publish_rate"):
            argVals['snoozePublishCycleLimit'] = int(validateIntParameter(arg,"snooze_publish_rate", argVals['snoozePublishCycleLimit']))
        elif opt in ("--wake_duration"):
            argVals['awakePublishLimit'] = int(validateIntParameter(arg,"wake_durations_secs", argVals['awakePublishLimit']*argVals['awakePublishCycleLimit'])/argVals['awakePublishCycleLimit'])

    #Validate the wake/snooze stuff
    if (argVals['snoozePublishCycleLimit'] < argVals['awakePublishCycleLimit']):
        print("--wake_publish_rate must be less than or equal to --snooze_publish_rate")
        sys.exit()
    if ((argVals['awakePublishLimit']*argVals['awakePublishCycleLimit'])<MIN_WAKE_DURATION_SECS):
        print("--wake_duration must be greater than {} seconds".format(MIN_WAKE_DURATION_SECS))
        sys.exit()

    argVals['classicHost'] = argVals['classicHost'].strip()
    argVals['classicName'] = argVals['classicName'].strip()
    argVals['mqttHost'] = argVals['mqttHost'].strip()
    argVals['mqttUser'] = argVals['mqttUser'].strip()



    log.info("classicHost = {}".format(argVals['classicHost']))
    log.info("classicPort = {}".format(argVals['classicPort']))
    log.info("classicName = {}".format(argVals['classicName']))
    log.info("mqttHost = {}".format(argVals['mqttHost']))
    log.info("mqttPort = {}".format(argVals['mqttPort']))
    log.info("mqttRoot = {}".format(argVals['mqttRoot']))
    log.info("mqttUser = {}".format(argVals['mqttUser']))
    log.info("mqttPassword = **********")
    #log.info("mqttPassword = {}".format("mqttPassword"))
    log.info("awakePublishCycleLimit = {}".format(argVals['awakePublishCycleLimit']))
    log.info("snoozePublishCycleLimit = {}".format(argVals['snoozePublishCycleLimit']))
    log.info("awakePublishLimit = {}".format(argVals['awakePublishLimit']))

    #Make sure the last character in the root is a "/"
    if (not argVals['mqttRoot'].endswith("/")):
        argVals['mqttRoot'] += "/"