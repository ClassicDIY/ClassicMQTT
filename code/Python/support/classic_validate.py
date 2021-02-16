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
# Handle the command line arguments
# --------------------------------------------------------------------------- # 
def handleArgs(argv,argVals):
    
    log = logging.getLogger('classic_mqtt')

    from classic_mqtt import MAX_WAKE_RATE, MIN_WAKE_RATE, MIN_WAKE_PUBLISHES
    
    # Get all the environment variables first, and then over-ride with arguments.
    envSetting = os.environ.get('CLASSIC')
    if envSetting != None:
        argVals['classicHost'] = validateHostnameParameter(envSetting, 'CLASSIC', argVals['classicHost'], log)

    envSetting = os.environ.get('CLASSIC_PORT')
    if envSetting != None:
        argVals['classicPort'] = validateIntParameter(envSetting, 'CLASSIC_PORT',argVals['classicPort'], log)

    envSetting = os.environ.get('CLASSIC_NAME')
    if envSetting != None:
        argVals['classicName'] = validateStrParameter(envSetting,'CLASSIC_NAME',argVals['classicName'], log)

    envSetting = os.environ.get('MQTT')
    if envSetting != None:
        argVals['mqttHost'] = validateHostnameParameter(envSetting,"MQTT",argVals['mqttHost'], log)

    envSetting = os.environ.get('MQTT_PORT')
    if envSetting != None:
        argVals['mqttPort'] = validateIntParameter(envSetting,"MQTT_PORT", argVals['mqttPort'], log)

    envSetting = os.environ.get('MQTT_ROOT')
    if envSetting != None:
        argVals['mqttRoot'] = validateStrParameter(envSetting,"MQTT_ROOT", argVals['mqttRoot'], log)

    envSetting = os.environ.get('MQTT_USER')
    if envSetting != None:
        argVals['mqttUser'] = validateStrParameter(envSetting,"MQTT_USER", argVals['mqttUser'], log)

    envSetting = os.environ.get('MQTT_PASS')
    if envSetting != None:
        argVals['mqttPassword'] = validateStrParameter(envSetting,"MQTT_PASS", argVals['mqttPassword'], log)

    envSetting = os.environ.get('AWAKE_PUBLISH_RATE')
    if envSetting != None:
        argVals['awakePublishRate']  = int(validateIntParameter(envSetting,"AWAKE_PUBLISH_RATE", argVals['awakePublishRate'], log))

    envSetting = os.environ.get('SNOOZE_PUBLISH_RATE')
    if envSetting != None:
        argVals['snoozePublishRate'] = int(validateIntParameter(envSetting,"SNOOZE_PUBLISH_RATE", argVals['snoozePublishRate'], log))

    envSetting = os.environ.get('AWAKE_PUBLISH_LIMIT')
    if envSetting != None:
        argVals['awakePublishLimit'] = int(validateIntParameter(envSetting,"AWAKE_PUBLISH_LIMIT", argVals['awakePublishLimit'], log))


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
            argVals['classicHost'] = validateHostnameParameter(arg,"classic",argVals['classicHost'], log)
        elif opt in ('--classic_port'):
            argVals['classicPort'] = validateIntParameter(arg,"classic_port", argVals['classicPort'], log)
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
        elif opt in ("--wake_publish_rate"):
            argVals['awakePublishRate'] = int(validateIntParameter(arg,"wake_publish_rate", argVals['awakePublishRate'], log))
        elif opt in ("--snooze_publish_rate"):
            argVals['snoozePublishRate'] = int(validateIntParameter(arg,"snooze_publish_rate", argVals['snoozePublishRate'], log))
        elif opt in ("--wake_publishes"):
            argVals['awakePublishLimit'] = int(validateIntParameter(arg,"wake_publishes", argVals['awakePublishLimit'], log))

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
    #log.info("mqttPassword = {}".format(argVals['mqttPassword']))
    log.info("awakePublishRate = {}".format(argVals['awakePublishRate']))
    log.info("snoozePublishRate = {}".format(argVals['snoozePublishRate']))
    log.info("awakePublishLimit = {}".format(argVals['awakePublishLimit']))

    #Make sure the last character in the root is a "/"
    if (not argVals['mqttRoot'].endswith("/")):
        argVals['mqttRoot'] += "/"
   
# --------------------------------------------------------------------------- # 
# Handle the Client command line arguments
# --------------------------------------------------------------------------- # 
def handleClientArgs(argv,argVals):

    log = logging.getLogger('classic_mqtt_client')

    # Get all the environment variables first, and then over-ride with arguments.
    envSetting = os.environ.get('CLASSIC_NAME')
    if envSetting != None:
        argVals['classicName'] = validateStrParameter(envSetting,'CLASSIC_NAME',argVals['classicName'], log)

    envSetting = os.environ.get('MQTT')
    if envSetting != None:
        argVals['mqttHost'] = validateHostnameParameter(envSetting,"MQTT",argVals['mqttHost'], log)

    envSetting = os.environ.get('MQTT_PORT')
    if envSetting != None:
        argVals['mqttPort'] = validateIntParameter(envSetting,"MQTT_PORT", argVals['mqttPort'], log)

    envSetting = os.environ.get('MQTT_ROOT')
    if envSetting != None:
        argVals['mqttRoot'] = validateStrParameter(envSetting,"MQTT_ROOT", argVals['mqttRoot'], log)

    envSetting = os.environ.get('MQTT_USER')
    if envSetting != None:
        argVals['mqttUser'] = validateStrParameter(envSetting,"MQTT_USER", argVals['mqttUser'], log)

    envSetting = os.environ.get('MQTT_PASS')
    if envSetting != None:
        argVals['mqttPassword'] = validateStrParameter(envSetting,"MQTT_PASS", argVals['mqttPassword'], log)


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
   