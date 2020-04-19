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
import sys
from random import randint, seed
from enum import Enum

from support.classic_modbusdecoder import getModbusData
from support.classic_jsonencoder import encodeClassicData_readings, encodeClassicData_info
from support.classic_validate import handleArgs
from timeloop import Timeloop
from datetime import timedelta

class PublishMode(Enum):
    Snoozing = 1
    Awake = 2
# --------------------------------------------------------------------------- # 
# GLOBALS
# --------------------------------------------------------------------------- # 
MAX_WAKE_PUB_INT_SECS       = 30        #in seconds
MIN_WAKE_PUB_INT_SECS       = 1         #in seconds
DEFAULT_WAKE_PUB_INT_SECS   = 5                          #in seconds
MIN_WAKE_DURATION_SECS      = 1*60                       #in seconds (1 minute)
DEFAULT_WAKE_DURATION_SECS  = 15*60                      #in seconds (15 minute)

MAX_SNOOZE_PUB_INT_SECS     = 4*60*60                    #in seconds (4 hours)
MIN_SNOOZE_PUB_INT_SECS     = 1*60                       #in seconds (1 minute)
DEFAULT_SNOOZE_PUB_INT_SECS = 5*60                       #in seconds (5 minutes)

MODBUS_MAX_ERROR_COUNT      = 300                        #Number of errors on the MODBUS before the tool exits
MQTT_MAX_ERROR_COUNT        = 300                        #Number of errors on the MQTT before the tool exits
MAIN_LOOP_SLEEP_SECS        = 5                          #Seconds to sleep in the main loop

# --------------------------------------------------------------------------- # 
# Default startup values. Can be over-ridden by command line options.
# --------------------------------------------------------------------------- # 
argumentValues = {'classicHost':"ClassicHost", 'classicPort':"502", 'classicName':"classic", \
                  'mqttHost':"127.0.0.1", 'mqttPort':"502", 'mqttRoot':"ClassicMQTT", 'mqttUser':"username", 'mqttPassword':"password", \
                  'awakePublishCycleLimit':DEFAULT_WAKE_PUB_INT_SECS, \
                  'snoozePublishCycleLimit':DEFAULT_SNOOZE_PUB_INT_SECS, \
                  'awakePublishLimit':DEFAULT_WAKE_DURATION_SECS}

# --------------------------------------------------------------------------- # 
# Counters and status variables
# --------------------------------------------------------------------------- # 
currentMode                 = PublishMode.Snoozing
infoPublished               = False
stayAwake                   = False
mqttConnected               = False
doStop                      = False

modbusErrorCount            = 0
mqttErrorCount              = 0
awakePublishCount           = 0                          #How many publishes have I done?
awakePublishCycles          = 0
snoozePublishCycles         = 0                          #How many cycles have gone by?

mqttClient                  = None

# --------------------------------------------------------------------------- # 
# configure the logging
# --------------------------------------------------------------------------- # 
log = logging.getLogger('classic_mqtt')
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
    global mqttConnected, mqttErrorCount, mqttClient
    if rc==0:
        log.debug("MQTT connected OK Returned code={}".format(rc))
        #subscribe to the commands
        try:
            topic = "{}{}/cmnd/#".format(argumentValues['mqttRoot'], argumentValues['classicName'])
            client.subscribe(topic)
            log.debug("Subscribed to {}".format(topic))
            
            #publish that we are Online
            will_topic = "{}{}/tele/LWT".format(argumentValues['mqttRoot'], argumentValues['classicName'])
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
    global mqttConnected, mqttClient
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

        global infoPublished, currentMode, doStop, mqttConnected, mqttErrorCount, awakePublishCount, awakePublishCycles, stayAwake

        mqttConnected = True #got a message so we must be up again...
        mqttErrorCount = 0

        msg = message.payload.decode(encoding='UTF-8').upper()
        log.debug("Received MQTT message {}".format(msg))

        #if we get a WAKE or INFO, reset the counters, re-puplish the INFO and stop snoozing.
        if msg == "{\"WAKE\"}" or msg == "{\"INFO\"}":
            #Make info packet get published
            infoPublished = False 
            currentMode = PublishMode.Awake
            awakePublishCount = 0 #reset the publish count

            # this will cause an immediate publish, no reason to wait for the cycles to expire
            awakePublishCycles = argumentValues['awakePublishCycleLimit'] 
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
    global mqttConnected, mqttErrorCount

    topic = "{}{}/stat/{}".format(argumentValues['mqttRoot'], argumentValues['classicName'], subtopic)
    log.debug("Publishing: {}".format(topic))
    
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
    global currentMode, snoozePublishCycles, infoPublished, awakePublishCycles, awakePublishCount, stayAwake
    #log.debug(currentMode)
    if (currentMode == PublishMode.Awake):
        #Has the number of cycles between each publish time passed (if you publish every 5 seconds, then 5 will go by)
        if (awakePublishCycles>=argumentValues['awakePublishCycleLimit']): 
            awakePublishCycles = 0 #reset awakePublishCycles

            #We remain awake for a number of publishes (calcluated from awake_duration)
            if awakePublishCount >= argumentValues['awakePublishLimit']:
                awakePublishCount = 0
                if stayAwake:
                    log.debug("StayAwake enabled, overriding going into snooze")
                    return True
                else:
                    currentMode = PublishMode.Snoozing
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
        # log.debug("snoozePuvlishCycles:{}".format(snoozePublishCycles))
        if (snoozePublishCycles >= argumentValues['snoozePublishCycleLimit']):
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
            data = getModbusData(argumentValues['classicHost'], argumentValues['classicPort'])
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
# Main
# --------------------------------------------------------------------------- # 
def run(argv):

    global doStop, mqttClient, awakePublishCycles, snoozePublishCycles

    log.info("classic_mqtt starting up...")

    handleArgs(argv, argumentValues, MIN_WAKE_DURATION_SECS)

    #Make it publish right away
    awakePublishCycles = argumentValues['awakePublishCycleLimit']
    snoozePublishCycles =  argumentValues['snoozePublishCycleLimit']

    #random seed from the OS
    seed(int.from_bytes( os.urandom(4), byteorder="big"))

    mqttErrorCount = 0

    #setup the MQTT Client for publishing and subscribing
    clientId = argumentValues['mqttUser'] + "_mqttclient_" + str(randint(100, 999))
    log.info("Connecting with clientId=" + clientId)
    mqttClient = mqttclient.Client(clientId) 
    mqttClient.username_pw_set(argumentValues['mqttUser'], password=argumentValues['mqttPassword'])
    mqttClient.on_connect = on_connect    
    mqttClient.on_disconnect = on_disconnect  
    mqttClient.on_message = on_message

    #Set Last Will 
    will_topic = "{}{}/tele/LWT".format(argumentValues['mqttRoot'], argumentValues['classicName'])
    mqttClient.will_set(will_topic, payload="Offline", qos=0, retain=False)

    try:
        log.info("Connecting to MQTT {}:{}".format(argumentValues['mqttHost'], argumentValues['mqttPort']))
        mqttClient.connect(host=argumentValues['mqttHost'],port=int(argumentValues['mqttPort'])) 
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