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
        assert len(param) < 255
        # Permit name to end with a single dot.
        hostname = param[:-1] if param.endswith('.') else param
        # check each hostname segment
        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        assert all(allowed.match(s) for s in hostname.split("."))
    except:
        log.error("Invalid parameter, {} passed for {}".format(param, name))
        return defaultValue
    try:
        socket.gethostbyname(param)
    except Exception as e:
        log.warning("Name resolution failed for {} passed for {}".format(param, name))
        log.exception(e, exc_info=False)
    return param

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
def handleArgs(argv,argVals):

    from classic_mqtt import MAX_WAKE_RATE, MIN_WAKE_RATE, MIN_WAKE_PUBLISHES
    
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
                     "wake_publishes="])
    except getopt.GetoptError:
        print("Error parsing command line parameters, please use: py --classic <{}> --classic_port <{}> --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --wake_publish_rate <{}> --snooze_publish_rate <{}> --wake_publishes <{}>".format( \
                    argVals['classicHost'], argVals['classicPort'], argVals['classicName'], argVals['mqttHost'], argVals['mqttPort'], argVals['mqttRoot'], argVals['awakePublishRate'], argVals['snoozePublishRate'], int(argVals['awakePublishLimit']*argVals['awakePublishRate'])))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ("Parameter help: py --classic <{}> --classic_port <{}> --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --wake_publish_rate <{}> --snooze_publish_rate <{}> --wake_publishes <{}>".format( \
                    argVals['classicHost'], argVals['classicPort'], argVals['classicName'], argVals['mqttHost'], argVals['mqttPort'], argVals['mqttRoot'], argVals['awakePublishRate'], argVals['snoozePublishRate'], int(argVals['awakePublishLimit']*argVals['awakePublishRate'])))
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
            argVals['awakePublishRate'] = int(validateIntParameter(arg,"wake_publish_rate", argVals['awakePublishRate']))
        elif opt in ("--snooze_publish_rate"):
            argVals['snoozePublishRate'] = int(validateIntParameter(arg,"snooze_publish_rate", argVals['snoozePublishRate']))
        elif opt in ("--wake_publishes"):
            argVals['awakePublishLimit'] = int(validateIntParameter(arg,"wake_publishes", argVals['awakePublishLimit']))

    #Validate the wake/snooze stuff
    if (argVals['snoozePublishRate'] < argVals['awakePublishRate']):
        print("--wake_publish_rate must be less than or equal to --snooze_publish_rate")
        sys.exit()
    
    if ((argVals['snoozePublishRate'] % argVals['awakePublishRate']) != 0):
        log.info("Set --snooze_publish_rate to an even multiple of --wake_publish_rate for most accurate timing of snooze cycles")

    if ((argVals['awakePublishRate'])<MIN_WAKE_RATE):
        print("--wake_publish_rate must be greater than or equal to {} seconds".format(MIN_WAKE_RATE))
        sys.exit()
    elif ((argVals['awakePublishRate'])>MAX_WAKE_RATE):
        print("--wake_publish_rate must be less than or equal to {} seconds".format(MAX_WAKE_RATE))
        sys.exit()

    if ((argVals['awakePublishLimit'])<MIN_WAKE_PUBLISHES):
        print("--wake_publishes must be greater than {} publishes".format(MIN_WAKE_PUBLISHES))
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
    log.info("awakePublishRate = {}".format(argVals['awakePublishRate']))
    log.info("snoozePublishRate = {}".format(argVals['snoozePublishRate']))
    log.info("awakePublishLimit = {}".format(argVals['awakePublishLimit']))

    #Make sure the last character in the root is a "/"
    if (not argVals['mqttRoot'].endswith("/")):
        argVals['mqttRoot'] += "/"
