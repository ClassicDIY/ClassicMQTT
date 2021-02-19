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
from time import time_ns


# --------------------------------------------------------------------------- # 
# GLOBALS
# --------------------------------------------------------------------------- # 
MAX_WAKE_RATE               = 15        #in seconds
MIN_WAKE_RATE               = 3         #in seconds
DEFAULT_WAKE_RATE           = 5         #in seconds
MIN_WAKE_PUBLISHES          = 15        #minimum number of publishes before snoozing this * wake_rate = time awake
DEFAULT_WAKE_PUBLISHES      = 60        #default number of publishes before switching to snooze

MAX_SNOOZE_RATE             = 4*60*60   #in seconds (4 hours)
MIN_SNOOZE_RATE             = 1*60      #in seconds (1 minute)
DEFAULT_SNOOZE_RATE         = 5*60      #in seconds (5 minutes)

MODBUS_MAX_ERROR_COUNT      = 300       #Number of errors on the MODBUS before the tool exits
MQTT_MAX_ERROR_COUNT        = 300       #Number of errors on the MQTT before the tool exits
MAIN_LOOP_SLEEP_SECS        = 5         #Seconds to sleep in the main loop

# --------------------------------------------------------------------------- # 
# Default startup values. Can be over-ridden by command line options.
# --------------------------------------------------------------------------- # 
argumentValues = { \
    'classicHost':os.getenv('CLASSIC', "ClassicHost"), \
    'classicPort':os.getenv('CLASSIC_PORT', "502"), \
    'classicName':os.getenv('CLASSIC_NAME', "classic"), \
    'mqttHost':os.getenv('MQTT_HOST', "127.0.0.1"), \
    'mqttPort':os.getenv('MQTT_PORT', "1883"), \
    'mqttRoot':os.getenv('MQTT_ROOT', "ClassicMQTT"), \
    'mqttUser':os.getenv('MQTT_USER', "ClassicPublisher"), \
    'mqttPassword':os.getenv('MQTT_PASS', "ClassicPub123"), \
    'awakePublishRate':int(os.getenv('AWAKE_PUBLISH_RATE', str(DEFAULT_WAKE_RATE))), \
    'snoozePublishRate':int(os.getenv('SNOOZE_PUBLISH_RATE', str(DEFAULT_SNOOZE_RATE))), \
    'awakePublishLimit':int(os.getenv('AWAKE_PUBLISH_LIMIT', str(DEFAULT_WAKE_PUBLISHES)))}

# --------------------------------------------------------------------------- # 
# Counters and status variables
# --------------------------------------------------------------------------- # 
infoPublished               = False
stayAwake                   = False
mqttConnected               = False
doStop                      = False
modeAwake                   = False

modbusErrorCount            = 0
mqttErrorCount              = 0
awakePublishCount           = 0      #How many publishes have I done?
awakePublishCycles          = 0
snoozePublishCycles         = 0      #How many cycles have gone by?
snoozeCycleLimit            = 0      #How many cycles before I publish in snooze mode (changes with wake rate)
currentPollRate             = DEFAULT_WAKE_RATE
mqttClient                  = None

# --------------------------------------------------------------------------- # 
# configure the logging
# --------------------------------------------------------------------------- # 
log = logging.getLogger('classic_mqtt')
if not log.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler) 
    log.setLevel(os.environ.get("LOGLEVEL", "DEBUG"))

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

        global currentPollRate, infoPublished, modeAwake, doStop, mqttConnected, mqttErrorCount, awakePublishCount, awakePublishCycles, stayAwake, argumentValues, snoozeCycleLimit

        mqttConnected = True #got a message so we must be up again...
        mqttErrorCount = 0

        msg = message.payload.decode(encoding='UTF-8').upper()
        log.debug("Received MQTT message {}".format(msg))

        #if we get a WAKE or INFO, reset the counters, re-puplish the INFO and stop snoozing.
        if msg == "{\"WAKE\"}" or msg == "{\"INFO\"}":
            #Make info packet get published
            infoPublished = False 
            modeAwake = True
            awakePublishCount = 0 #reset the publish count

            # this will cause an immediate publish, no reason to wait for the cycles to expire
            awakePublishCycles = argumentValues['awakePublishRate'] 
        elif msg == "{\"STOP\"}":
            doStop = True
        else: #JSON messages
            theMessage = json.loads(message.payload.decode(encoding='UTF-8'))
            log.debug(theMessage)
            
            if "stayAwake" in theMessage:
                stayAwake = theMessage['stayAwake']
                log.debug("StayAwake received, setting stayAwake to {}".format(stayAwake))
            
            if "wakePublishRate" in theMessage:
                newRate_msecs = theMessage['wakePublishRate']
                newRate = round(newRate_msecs/1000)
                if newRate < MIN_WAKE_RATE:
                    log.error("Received wakePublishRate of {} which is below minimum of {}".format(newRate,MIN_WAKE_RATE))
                elif newRate > MAX_WAKE_RATE:
                    log.error("Received wakePublishRate of {} which is above maximum of {}".format(newRate,MAX_WAKE_RATE))
                else:
                    argumentValues['awakePublishRate'] = newRate
                    currentPollRate = newRate
                    snoozeCycleLimit = round(argumentValues['snoozePublishRate']/argumentValues['awakePublishRate'])
                    log.debug("wakePublishRate message received, setting rate to {}".format(newRate))
                    log.debug("Updating snoozeCycleLimit to {}".format(snoozeCycleLimit))
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
    global modeAwake, snoozePublishCycles, infoPublished, awakePublishCycles, awakePublishCount, stayAwake, argumentValues
    #log.debug("modeAwake: {}".format(modeAwake))
    if (modeAwake):
        #We remain awake for a number of publishes
        #log.debug("awakePublishCount:{}".format(awakePublishCount))
        #log.debug("awakePublishLimit:{}".format(argumentValues['awakePublishLimit']))
        if awakePublishCount >= argumentValues['awakePublishLimit']:
            awakePublishCount = 0
            if stayAwake:
                log.debug("StayAwake enabled, so not going into snooze mode")
                return True
            else:
                modeAwake = False
                snoozePublishCycles = 0
                return False
        else:
            awakePublishCount += 1
            return True
    else: #Snoozing
        # We passively publish every snoozePublishCycles while snoozing
        # log.debug("snoozePublishCycles:{}".format(snoozePublishCycles))
        
        if (snoozePublishCycles >= snoozeCycleLimit):
            infoPublished = False #Makes #info# get published
            snoozePublishCycles = 0 #Reset the cycles to start again
            return True
        else:
            snoozePublishCycles += 1
            return False
# --------------------------------------------------------------------------- # 
# Periodic will be called when needed.
# If so, it will read from MODBUS and publish to MQTT
# --------------------------------------------------------------------------- # 
def periodic(modbus_stop):    

    global mqttClient, modbusErrorCount, infoPublished, mqttErrorCount, currentPollRate

    if not modbus_stop.is_set():
        #Get the current time as a float of seconds.
        beforeTime = time_ns() /  1000000000.0

        #log.debug("in Periodic")
        try:
            if timeToPublish() and mqttConnected:
                data = {}
                #Get the Modbus Data and store it.
                data = getModbusData(modeAwake, argumentValues['classicHost'], argumentValues['classicPort'])
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

        #Account for the time that has been spent on this cycle to do the actual work
        timeUntilNextInterval = currentPollRate - (time_ns()/1000000000.0 - beforeTime)

        # If doing the work took too long, skip as many polling forward so that we get a time in the future.
        while (timeUntilNextInterval < 0):
            log.debug("Adjusting next interval to account for cycle taking too long: {}".format(timeUntilNextInterval))
            timeUntilNextInterval = timeUntilNextInterval + currentPollRate 
            log.debug("Adjusted interval: {}".format(timeUntilNextInterval))

        #log.debug("Next Interval: {}".format(timeUntilNextInterval))
        # set myself to be called again in correct number of seconds
        threading.Timer(timeUntilNextInterval, periodic, [modbus_stop]).start()

# --------------------------------------------------------------------------- # 
# Main
# --------------------------------------------------------------------------- # 
def run(argv):

    global doStop, mqttClient, awakePublishCycles, snoozePublishCycles, currentPollRate, snoozeCycleLimit

    log.info("classic_mqtt starting up...")

    handleArgs(argv, argumentValues)

    snoozeCycleLimit = round(argumentValues['snoozePublishRate']/argumentValues['awakePublishRate'])
    log.debug("snoozeCycleLimit: {}".format(snoozeCycleLimit))

    #Make it publish right away
    awakePublishCycles = argumentValues['awakePublishRate']
    snoozePublishCycles =  argumentValues['snoozePublishRate']

    currentPollRate = argumentValues['awakePublishRate']

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


    #define the stop for the function
    periodic_stop = threading.Event()
    # start calling periodic now and every 
    periodic(periodic_stop)

    log.debug("Starting main loop...")
    while not doStop:
        try:            
            time.sleep(MAIN_LOOP_SLEEP_SECS)
            #check to see if shutdown received
            if modbusErrorCount > MODBUS_MAX_ERROR_COUNT:
                log.error("MODBUS error count exceeded, exiting...")
                doStop = True
            
            if not mqttConnected:
                if (mqttErrorCount > MQTT_MAX_ERROR_COUNT):
                    log.error("MQTT Error count exceeded, disconnected, exiting...")
                    doStop = True

        except KeyboardInterrupt:
            log.error("Got Keyboard Interuption, exiting...")
            doStop = True
        except Exception as e:
            log.error("Caught other exception...")
            log.exception(e, exc_info=True)
    
    log.info("Exited the main loop, stopping other loops")
    log.info("Stopping periodic async...")
    periodic_stop.set()

    log.info("Stopping MQTT loop...")
    mqttClient.loop_stop()

    log.info("Exiting classic_mqtt")

if __name__ == '__main__':
    run(sys.argv[1:])