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
DEFAULT_PULSE_RATE        = 5         #Periodic gets called every this many seconds
DEFAULT_SNOOZE_CYCLES     = 60        #When nobody is listening, snooze this many cycles
DEFAULT_WAKE_COUNT        = 60        #The number of times to publish at the fast rate after getting a "wake"
MODBUS_MAX_ERROR_COUNT    = 300       #Number of errors on the MODBUS before the tool exits
MQTT_MAX_ERROR_COUNT      = 300       #Number of errors on the MQTT before the tool exits
MAIN_LOOP_SLEEP_SECS      = 5         #Seconds to sleep in the main loop

wakeCount                 = 0
infoPublished             = True
snoozeCycles              = DEFAULT_SNOOZE_CYCLES
snoozeCount               = 0
snoozing                  = True
modbusErrorCount          = 0

mqttConnected             = False
mqttErrorCount            = 0
mqttClient               = None

doStop                    = False

# --------------------------------------------------------------------------- # 
# Default startup values. Can be over-ridden by command line options.
# --------------------------------------------------------------------------- # 
classicHost               = "ClassicHost"       #Default Classic
classicPort               = "502"               #Default MODBUS port
classicName               = "Classic"           #Default Classic Name
mqttHost                  = "127.0.0.1"         #Defult MQTT host
mqttPort                  = 1883                #Default MQTT port
mqttRoot                  = "ClassicMQTT"       #Dfault Root to publish on
mqttUser                  = "username"          #Default user
mqttPassword              = "password"          #Default password

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

        global wakeCount, infoPublished, snoozing, doStop, mqttConnected, mqttErrorCount

        mqttConnected = True #got a message so we must be up again...
        mqttErrorCount = 0

        msg = message.payload.decode(encoding='UTF-8').upper()
        log.debug("Received MQTT message {}".format(msg))

        #if we get a WAKE or INFO, reset the counters, re-puplish the INFO and stop snoozing.
        if msg == "{\"WAKE\"}" or msg == "{\"INFO\"}":
            wakeCount = 0
            infoPublished = False
            snoozing = False
        elif msg == "{\"STOP\"}":
            doStop = True
        else:
            log.error("on_message: Received something else")
            

# --------------------------------------------------------------------------- # 
# MQTT Publish the data
# --------------------------------------------------------------------------- # 
def mqttPublish(client, data, subtopic):
    global mqttRoot, mqttConnected, mqttErrorCount

    topic = "{}/{}/stat/{}".format(mqttRoot, classicName, subtopic)
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
# Test to see if it is time to gather data and publish
# --------------------------------------------------------------------------- # 
def timeToPublish():
    global snoozing, snoozeCount, wakeCount, infoPublished
    if snoozing:
        if (snoozeCount >= snoozeCycles):
            infoPublished = False
            snoozeCount = 0
            return True
        else:
            snoozeCount += 1
            return False
    else:
        wakeCount += 1
        if wakeCount >= DEFAULT_WAKE_COUNT:
            snoozing = True
            wakeCount = 0
        return True

# --------------------------------------------------------------------------- # 
# Periodic will be called every so often to read from MODBUS and publish to MQTT
# --------------------------------------------------------------------------- # 
@tl.job(interval=timedelta(seconds=DEFAULT_PULSE_RATE))
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
    
    global classicHost, classicPort, classicName, mqttHost, mqttPort, mqttRoot, mqttUser, mqttPassword, snoozeCycles

    try:
      opts, args = getopt.getopt(argv,"h",["classic=","classic_port=","classic_name=","mqtt=","mqtt_port=","mqtt_root=","mqtt_user=","mqtt_pass=","snooze_secs="])
    except getopt.GetoptError:
        print ("classic_mqtt.py --classic <{}> --classic_port <{}> --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --snooze_secs <{}>".format(classicHost, classicPort, classicName, mqttHost, mqttPort, mqttRoot, snoozeCycles*DEFAULT_PULSE_RATE))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ("classic_mqtt.py --classic <{}> --classic_port <{}> --classic_name <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --mqtt_user <username> --mqtt_pass <password> --snooze_secs <{}>".format(classicHost, classicPort, classicName, mqttHost, mqttPort, mqttRoot, snoozeCycles*DEFAULT_PULSE_RATE))
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
        elif opt in ("--snooze_secs"):
            snoozeCycles = int(validateIntParameter(arg,"snooze_secs", int(snoozeCycles*DEFAULT_PULSE_RATE))/DEFAULT_PULSE_RATE)


    log.info("classicHost = {}".format(classicHost))
    log.info("classicPort = {}".format(classicPort))
    log.info("classicName = {}".format(classicName))
    log.info("mqttHost = {}".format(mqttHost))
    log.info("mqttPort = {}".format(mqttPort))
    log.info("mqttRoot = {}".format(mqttRoot))
    log.info("mqttUser = {}".format(mqttUser))
    log.info("mqttPassword = **********")
    #log.info("mqttPassword = {}".format("mqttPassword"))
    log.info("snoozeCycles = {}".format(snoozeCycles))

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