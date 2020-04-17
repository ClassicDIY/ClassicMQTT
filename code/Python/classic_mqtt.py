#!/usr/bin/python3

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from paho.mqtt import client as mqttclient
from collections import OrderedDict
import json
import time
import socket
import threading
import logging
import os
import sys, getopt
from random import randint, seed

from support.classic_modbusdecoder import getModbusData
from support.classic_jsonencoder import encodeClassicData_readings, encodeClassicData_info
from support.classic_validate import validateIntParameter, validateURLParameter, validateStrParameter
from timeloop import Timeloop
from datetime import timedelta

# --------------------------------------------------------------------------- # 
# GLOBALS
# --------------------------------------------------------------------------- # 
MAX_WAKE_PUB_INT_SECS       = 30        #in seconds
MIN_WAKE_PUB_INT_SECS       = 1         #in seconds
DEFAULT_WAKE_PUB_INT_SECS   = 5         #in seconds
MIN_WAKE_DURATION_SECS  = 1*60          #in seconds (1 minute)

MAX_SNOOZE_PUB_INT_SECS     = 4*60*60   #in seconds (4 hours)
MIN_SNOOZE_PUB_INT_SECS     = 1*60      #in seconds (1 minute)
DEFAULT_SNOOZE_PUB_INT_SECS = 5*60      #in seconds (5 minutes)

MODBUS_MAX_ERROR_COUNT      = 300       #Number of errors on the MODBUS before the tool exits
MQTT_MAX_ERROR_COUNT        = 300       #Number of errors on the MQTT before the tool exits
MAIN_LOOP_SLEEP_SECS        = 5         #Seconds to sleep in the main loop

awakePublishLimit    = MIN_WAKE_DURATION_SECS #How many times to publish before sleeping.
awakePublishCount            = 0 #Home many publishes have I done?

awakePublishCycleLimit   = DEFAULT_WAKE_PUB_INT_SECS #Publish every this many cycles
awakePublishCycles           = 0

snoozePublishCycleLimit     = DEFAULT_SNOOZE_PUB_INT_SECS #When snoozing, publish every this many cycles.
snoozePublishCycles          = 0 #How many cycles have gone by?

snoozing                    = True
stayAwake                   = False


infoPublished              = True
modbusErrorCount           = 0
mqttConnected             = False
mqttErrorCount            = 0
mqttClient                = None

doStop                    = False

# --------------------------------------------------------------------------- # 
# Default startup values. Can be over-ridden by command line options.
# --------------------------------------------------------------------------- # 
classicHost               = "ClassicHost"       #Default Classic
classicPort               = "502"               #Default MODBUS port
classicName               = "classic"           #Default Classic Name
mqttHost                  = "127.0.0.1"         #Defult MQTT host
mqttPort                  = 1883                #Default MQTT port
mqttRoot                  = "ClassicMQTT"       #Dfault Root to publish on
mqttUser                  = "username"          #Default user
mqttPassword              = "password"          #Default password
snoozePublishSecs         = DEFAULT_SNOOZE_PUB_INT_SECS #Every this many seconds
wakePublishSecs           = DEFAULT_WAKE_PUB_INT_SECS   #Every this many seconds
wakeDurationSecs          = MIN_WAKE_DURATION_SECS #Stay awake this long after a "WAKE" or "INFO"


# --------------------------------------------------------------------------- # 
# configure the logging
# --------------------------------------------------------------------------- # 
log = logging.getLogger('classic_mqtt')
#handler = RotatingFileHandler(os.environ.get("LOGFILE", "./classic_mqtt.log"), maxBytes=5*1024*1024, backupCount=5)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
handler.setFormatter(formatter)
log.addHandler(handler) 
log.setLevel(os.environ.get("LOGLEVEL", "DEBUG"))

tl = Timeloop()

# --------------------------------------------------------------------------- # 
# MQTT On Connect function
# --------------------------------------------------------------------------- # 
def on_connect(client, userdata, flags, rc):
    global mqttConnected, mqttErrorCount
    if rc==0:
        log.debug("MQTT connected OK Returned code={}".format(rc))
        #subscribe to the commands
        try:
            topic = "{}{}/cmnd/#".format(mqttRoot, classicName)
            client.subscribe(topic)
            log.debug("Subscribed to {}".format(topic))
            
            #publish that we are Online
            will_topic = "{}{}/tele/LWT".format(mqttRoot, classicName)
            mqttClient.publish(will_topic, "Online",  qos=0, retain=False)
        except Exception as e:
            log.error("MQTT Subscribe failed")
            log.exception(e, exc_info=True)

        mqttConnected = True
        mqttErrorCount = 0
    else:
        mqttConnected = False
        log.error("MQTT Bad connection Returned code={}".format(rc))

# --------------------------------------------------------------------------- # 
# MQTT On Disconnect
# --------------------------------------------------------------------------- # 
def on_disconnect(client, userdata, rc):
    global mqttConnected
    mqttConnected = False
    #if disconnetion was unexpectred (not a result of a disconnect request) then log it.
    if rc!=mqttclient.MQTT_ERR_SUCCESS:
        log.debug("on_disconnect: Disconnected. ReasonCode={}".format(rc))

# --------------------------------------------------------------------------- # 
# MQTT On Message
# --------------------------------------------------------------------------- # 
def on_message(client, userdata, message):
        #print("Received message '" + str(message.payload) + "' on topic '"
        #+ message.topic + "' with QoS " + str(message.qos))

        global infoPublished, snoozing, doStop, mqttConnected, mqttErrorCount, awakePublishCount, awakePublishCycles, stayAwake

        mqttConnected = True #got a message so we must be up again...
        mqttErrorCount = 0

        msg = message.payload.decode(encoding='UTF-8').upper()
        log.debug("Received MQTT message {}".format(msg))

        #if we get a WAKE or INFO, reset the counters, re-puplish the INFO and stop snoozing.
        if msg == "{\"WAKE\"}" or msg == "{\"INFO\"}":
            #Make info packet get published
            infoPublished = False 
            snoozing = False
            awakePublishCount = 0 #reset the publish count

            # this will cause an immediate publish, no reason to wait for the cycles to expire
            awakePublishCycles = awakePublishCycleLimit 
        elif msg == "{\"STAYAWAKE:TRUE\"}":
            log.debug("StayAwake:true received, setting stayAwake true")
            stayAwake = True
        elif msg == "{\"STAYAWAKE:FALSE\"}":
            log.debug("StayAwake:false received, setting stayAwake false")
            stayAwake = False
        elif msg == "{\"STOP\"}":
            doStop = True
        else:
            log.error("on_message: Received something else")
            

# --------------------------------------------------------------------------- # 
# MQTT Publish the data
# --------------------------------------------------------------------------- # 
def mqttPublish(client, data, subtopic):
    global mqttRoot, mqttConnected, mqttErrorCount

    topic = "{}{}/stat/{}".format(mqttRoot, classicName, subtopic)
    log.debug(topic)
    
    try:
        client.publish(topic,data)
        return True
    except Exception as e:
        log.error("MQTT Publish Error Topic:{}".format(topic))
        log.exception(e, exc_info=True)
        mqttConnected = False
        return False


# --------------------------------------------------------------------------- # 
# Test to see if it is time to gather data and publish.
# periodic is called every second, so this method figures out if it is time to 
# publish based on the mode (awake or snoozing) and the frequency rates
# --------------------------------------------------------------------------- # 
def timeToPublish():
    global snoozing, snoozePublishCycles, infoPublished, snoozePublishCycleLimit, \
           awakePublishCycleLimit, awakePublishCycles, awakePublishCount, stayAwake

    if (not snoozing):
        #Has the number of cycles between each publish time passed (if you publish every 5 seconds, then 5 will go by)
        if (awakePublishCycles>=awakePublishCycleLimit): 
            awakePublishCycles = 0 #reset awakePublishCycles

            #We remain awake for a number of publishes (calcluated from awake_duration)
            if awakePublishCount >= awakePublishLimit:
                awakePublishCount = 0
                if stayAwake:
                    log.debug("StayAwake enabled, overriding going into snooze")
                    return True
                else:
                    snoozing = True
                    snoozePublishCycles = 0
                    return False
            else:
                awakePublishCount =+ 1
                return True
        else:
            awakePublishCycles += 1
            return False
    else: #Snoozing
        # We passively publish every snoozePublishCycles while snoozing
        if (snoozePublishCycles >= snoozePublishCycleLimit):
            infoPublished = False #Makes #info# get published
            snoozePublishCycles = 0 #Reset the cycles to start again
            return True
        else:
            snoozePublishCycles += 1
            return False


# --------------------------------------------------------------------------- # 
# Periodic will be called every 1 second to and check if a publish is needed.
# If so, it will read from MODBUS and publish to MQTT
# --------------------------------------------------------------------------- # 
@tl.job(interval=timedelta(seconds=1))
def periodic():
    global mqttClient, modbusErrorCount, infoPublished, mqttErrorCount
    #log.debug("in Periodic")
    try:
        if timeToPublish() and mqttConnected:
            data = {}
            #Get the Modbus Data and store it.
            data = getModbusData(classicHost, classicPort)
            if data: # got data
                modbusErrorCount = 0

                if mqttPublish(mqttClient,encodeClassicData_readings(data),"readings"):
                    if (not infoPublished): #Check if the Info has been published yet
                        if mqttPublish(mqttClient,encodeClassicData_info(data),"info"):
                            infoPublished = True                        
                        else:
                            mqttErrorCount += 1
                else:
                    mqttErrorCount += 1

            else:
                log.error("MODBUS data not good, skipping publish")
                modbusErrorCount += 1
    except Exception as e:
        log.error("Caught Error in periodic")
        log.exception(e, exc_info=True)



# --------------------------------------------------------------------------- # 
# Handle the command line arguments
# --------------------------------------------------------------------------- # 
def handleArgs(argv):
    
    global classicHost, classicPort, classicName, mqttHost, mqttPort, mqttRoot, mqttUser, \
           mqttPassword, awakePublishCycleLimit, snoozePublishCycleLimit, awakePublishLimit

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
        print("Error parsing command line parameters, please use: classic_mqtt.py --classic <{}> --classic_port <{}> --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --wake_publish_rate <{}> --snooze_publish_rate <{}> --wake_duration <{}>".format( \
                    classicHost, classicPort, classicName, mqttHost, mqttPort, mqttRoot, awakePublishCycleLimit, snoozePublishCycleLimit, int(awakePublishLimit*awakePublishCycleLimit)))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ("Parameter help: classic_mqtt.py --classic <{}> --classic_port <{}> --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --wake_publish_rate <{}> --snooze_publish_rate <{}> --wake_duration <{}>".format( \
                        classicHost, classicPort, classicName, mqttHost, mqttPort, mqttRoot, awakePublishCycleLimit, snoozePublishCycleLimit, int(awakePublishLimit*awakePublishCycleLimit)))
            sys.exit()
        elif opt in ('--classic'):
            classicHost = validateURLParameter(arg,"classic",classicHost)
        elif opt in ('--classic_port'):
            classicPort = validateIntParameter(arg,"classic_port", classicPort)
        elif opt in ('--classic_name'):
            classicName = validateStrParameter(arg,"classic_name", classicName)
        elif opt in ("--mqtt"):
            mqttHost = validateURLParameter(arg,"mqtt",mqttHost)
        elif opt in ("--mqtt_port"):
            mqttPort = validateIntParameter(arg,"mqtt_port", mqttPort)
        elif opt in ("--mqtt_root"):
            mqttRoot = validateStrParameter(arg,"mqtt_root", mqttRoot)
        elif opt in ("--mqtt_user"):
            mqttUser = validateStrParameter(arg,"mqtt_user", mqttUser)
        elif opt in ("--mqtt_pass"):
            mqttPassword = validateStrParameter(arg,"mqtt_pass", mqttPassword)
        elif opt in ("--wake_publish_rate"):
            awakePublishCycleLimit = int(validateIntParameter(arg,"wake_publish_rate", awakePublishCycleLimit))
        elif opt in ("--snooze_publish_rate"):
            snoozePublishCycleLimit = int(validateIntParameter(arg,"snooze_publish_rate", snoozePublishCycleLimit))
        elif opt in ("--wake_duration"):
            awakePublishLimit = int(validateIntParameter(arg,"wake_durations_secs", awakePublishLimit*awakePublishCycleLimit)/awakePublishCycleLimit)

    #Validate the wake/snooze stuff
    if (snoozePublishCycleLimit < awakePublishCycleLimit):
        print("--wake_publish_rate must be less than or equal to --snooze_publish_rate")
        sys.exit()
    if ((awakePublishLimit*awakePublishCycleLimit)<MIN_WAKE_DURATION_SECS):
        print("--wake_duratio must be greater than {} seconds".format(MIN_WAKE_DURATION_SECS))
        sys.exit()


    log.info("classicHost = {}".format(classicHost))
    log.info("classicPort = {}".format(classicPort))
    log.info("classicName = {}".format(classicName))
    log.info("mqttHost = {}".format(mqttHost))
    log.info("mqttPort = {}".format(mqttPort))
    log.info("mqttRoot = {}".format(mqttRoot))
    log.info("mqttUser = {}".format(mqttUser))
    log.info("mqttPassword = **********")
    #log.info("mqttPassword = {}".format("mqttPassword"))
    log.info("awakePublishCycleLimit = {}".format(awakePublishCycleLimit))
    log.info("snoozePublishCycleLimit = {}".format(snoozePublishCycleLimit))
    log.info("awakePublishLimit = {}".format(awakePublishLimit))

    sys.exit(0)    

# --------------------------------------------------------------------------- # 
# Main
# --------------------------------------------------------------------------- # 
def run(argv):

    global doStop, mqttRoot, mqttConnected, mqttClient

    log.info("classic_mqtt starting up...")

    handleArgs(argv)
    if (mqttRoot.endswith("/") == False):
        mqttRoot += "/"
    #random seed from the OS
    random_data = os.urandom(4) 
    ranSeed = int.from_bytes(random_data, byteorder="big") 
    seed(ranSeed)

    mqttErrorCount = 0

    #setup the MQTT Client for publishing and subscribing
    clientId = mqttUser + "_mqttclient_" + str(randint(100, 999))
    log.info("Connecting with clientId=" + clientId)
    mqttClient = mqttclient.Client(clientId) 
    mqttClient.username_pw_set(mqttUser, password=mqttPassword)
    mqttClient.on_connect = on_connect    
    mqttClient.on_disconnect = on_disconnect  
    mqttClient.on_message = on_message

    #Set Last Will 
    will_topic = "{}{}/tele/LWT".format(mqttRoot, classicName)
    mqttClient.will_set(will_topic, payload="Offline", qos=0, retain=False)

    try:
        log.info("Connecting to MQTT {}:{}".format(mqttHost, mqttPort))
        mqttClient.connect(host=mqttHost,port=int(mqttPort)) 
    except Exception as e:
        log.error("Unable to connect to MQTT, exiting...")
        sys.exit(2)

    
    mqttClient.loop_start()

    #Setup the Timeloop stuff so periodic gets called every 5 seconds
    tl.start(block=False)

    keepLooping = True

    log.debug("Starting main loop...")
    while keepLooping:
        try:
            time.sleep(MAIN_LOOP_SLEEP_SECS)
            #check to see if shutdown received
            if doStop:
                log.info("Stopping...")
                keepLooping = False
            
            if modbusErrorCount > MODBUS_MAX_ERROR_COUNT:
                log.error("MODBUS not connected, exiting...")
                keepLooping = False
            
            if not mqttConnected:
                if (mqttErrorCount > MQTT_MAX_ERROR_COUNT):
                    log.error("MQTT Error count exceeded, disconnected, exiting...")
                    keepLooping = False

        except KeyboardInterrupt:
            log.error("Got Keyboard Interuption, exiting...")
            doStop = True
        except Exception as e:
            log.error("Caught other exception...")
            log.exception(e, exc_info=True)
    
    log.info("Stopping periodic async...")
    tl.stop()
    log.info("Stopping MQTT loop...")
    mqttClient.loop_stop()

    log.info("Exiting classic_mqtt")

if __name__ == '__main__':
    run(sys.argv[1:])