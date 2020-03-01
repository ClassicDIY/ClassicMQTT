#!/usr/bin/env/python

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from paho.mqtt import client as mqttclient
from collections import OrderedDict
import json
import time
import threading
import logging
from logging.handlers import formatter, handlers, RotatingFileHandler
import os
import sys, getopt

from support.classic_modbusdecoder import getModbusData
from support.classic_jsonencoder import encodeClassicData_readings, encodeClassicData_info


# --------------------------------------------------------------------------- # 
# GLOBALS
# --------------------------------------------------------------------------- # 
MODBUS_POLL_RATE          = 5                   #Get data from the Classic every 5 seconds
MQTT_PUBLISH_RATE         = 5                   #Check to see if anything needs publishing every 5 seconds.
MQTT_SNOOZE_COUNT         = 60                  #When no one is listening, publish every 5 minutes
WAKE_COUNT                = 60                  #The number of times to publish after getting a "wake"
MODBUS_MAX_ERROR_COUNT    = 300
MQTT_MAX_ERROR_COUNT      = 300
MAIN_LOOP_SLEEP           = 5                   #Seconds to sleep in the main loop

wakeCount                 = 0
infoPublished             = True
snoozeCount               = 0
snoozing                  = True
modbusErrorCount          = 0

mqttConnected             = False
mqttErrorCount            = 0

doStop                    = False

classicHost               = "ClassicHost"
classicPort               = "502"
mqttHost                  = "127.0.0.1"
mqttPort                  = 1883
mqttRoot                  = "ClassicMQTT"
mqttUser                  = "username"
mqttPassword              = "password"


# --------------------------------------------------------------------------- # 
# configure the logging
# --------------------------------------------------------------------------- # 
log = logging.getLogger('classic_mqtt')
#handler = logging.FileHandler('./classic_mqtt.log')
handler = RotatingFileHandler(os.environ.get("LOGFILE", "./classic_mqtt.log"), maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
handler.setFormatter(formatter)
log.addHandler(handler) 
log.setLevel(os.environ.get("LOGLEVEL", "DEBUG"))


# --------------------------------------------------------------------------- # 
# MQTT On Connect function
# --------------------------------------------------------------------------- # 
def on_connect(client, userdata, flags, rc):
    global mqttConnected, mqttErrorCount
    if rc==0:
        log.debug("MQTT connected OK Returned code={}".format(rc))
        #subscribe to the commands
        try:
            topic = "{}/classic/cmnd/#".format(mqttRoot)
            client.subscribe(topic)
            log.debug("Subscribed to {}".format(topic))
        except:
            e = sys.exc_info()[0]
            log.error("MQTT Subscribe failed e:{}".format(e))

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
    log.debug("on_disconnect: Disconnected")

# --------------------------------------------------------------------------- # 
# MQTT On Message
# --------------------------------------------------------------------------- # 
def on_message(client, userdata, message):
        #print("Received message '" + str(message.payload) + "' on topic '"
        #+ message.topic + "' with QoS " + str(message.qos))

        global wakeCount, infoPublished, snoozing, doStop, mqttConnected, mqttErrorCount

        mqttConnected = True #got a message so we must be up again...
        mqttErrorCount = 0

        msg = message.payload.decode(encoding='UTF-8')
        msg = msg.upper()

        log.debug("Recived MQTT message {}".format(msg))

        #if we get a WAKE or INFO, reset the counters and re-pulish the INFO.
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

    topic = "{}/classic/stat/{}".format(mqttRoot, subtopic)
    log.debug(topic)
    
    try:
        client.publish(topic,data)
        return True
    except:
        mqttConnected = False
        e = sys.exc_info()[0]
        log.error("MQTT Publish Error Topic:{} e:{}".format(topic, e))
        return False


# --------------------------------------------------------------------------- # 
# Test the snoozing etc to see if it is time to publish
# --------------------------------------------------------------------------- # 
def timeToPublish():
    global snoozing, snoozeCount, wakeCount, infoPublished
    if snoozing:
        if (snoozeCount >= MQTT_SNOOZE_COUNT):
            infoPublished = False
            snoozeCount = 0
            return True
        else:
            snoozeCount += 1
            return False
    else:
        wakeCount += 1
        if wakeCount >= WAKE_COUNT:
            snoozing = True
            wakeCount = 0
        return True

# --------------------------------------------------------------------------- # 
# Async called to read from MODBUS and publish to MQTT
# --------------------------------------------------------------------------- # 
def periodic(periodic_stop, client):
    global modbusErrorCount, infoPublished, mqttErrorCount
    if not periodic_stop.is_set():
        try:
            if timeToPublish() and mqttConnected:
                data = {}
                #Get the Modbus Data and store it.
                data = getModbusData(classicHost, classicPort)
                if data: # got data
                    modbusErrorCount = 0

                    if mqttPublish(client,encodeClassicData_readings(data),"readings"):
                        if (not infoPublished): #Check if the Info has been published yet
                            if mqttPublish(client,encodeClassicData_info(data),"info"):
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


        # set myself to be called again in correct number of seconds
        threading.Timer(MODBUS_POLL_RATE, periodic, [periodic_stop, client]).start()


# --------------------------------------------------------------------------- # 
# Handle the command line arguments
# --------------------------------------------------------------------------- # 
def handleArgs(argv):
    
    global classicHost, classicPort,mqttHost, mqttPort, mqttRoot, mqttUser, mqttPassword

    classic = classicHost
    classic_port = classicPort
    mqtt = mqttHost
    mqtt_port = mqttPort
    mqtt_root = mqttRoot
    username = mqttUser
    password = mqttPassword

    try:
      opts, args = getopt.getopt(argv,"h",["classic=","classic_port=","mqtt=","mqtt_port=","mqtt_root=","user=","pass="])
    except getopt.GetoptError:
        print ("classic_mqtt.py --classic <{}> --classic_port <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --user <username> --pass <password>".format(classic, classic_port, mqtt, mqtt_port, mqtt_root))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ("classic_mqtt.py --classic <{}> --classic_port <{}> --mqtt <{}> --mqtt_port <{}> --mqtt_root <{}> --user <username> --pass <password>".format(classic, classic_port, mqtt, mqtt_port, mqtt_root))
            sys.exit()
        elif opt in ('--classic'):
            classic = arg
        elif opt in ('--classic_port'):
            classic_port = arg
        elif opt in ("--mqtt"):
            mqtt = arg
        elif opt in ("--mqtt_port"):
            mqtt_port = arg
        elif opt in ("--mqtt_root"):
            mqtt_root = arg
        elif opt in ("--user"):
            username = arg
        elif opt in ("--pass"):
            password = arg

    log.debug("classic is {}".format(classic))
    log.debug("classic_port is {}".format(classic_port))
    log.debug("mqtt is {}".format(mqtt))
    log.debug("mqtt_port is {}".format(mqtt_port))
    log.debug("mqtt_root is {}".format(mqtt_root))
    log.debug("username is {}".format(username))
    log.debug("password is {}".format(password))

    classicHost = classic
    classicPort = classic_port
    mqttHost = mqtt
    mqttPort = mqtt_port
    mqttRoot = mqtt_root
    mqttUser = username
    mqttPassword = password

# --------------------------------------------------------------------------- # 
# Main
# --------------------------------------------------------------------------- # 
def run(argv):

    global doStop, mqttRoot, mqttConnected

    log.info("classic_mqtt is starting up...")

    handleArgs(argv)

    mqttErrorCount = 0
    #setup the MQTT Client for publishing and subscribing
    mqtt_client = mqttclient.Client(mqttUser+"_mqttclient") 
    mqtt_client.username_pw_set(mqttUser, password=mqttPassword)
    mqtt_client.on_connect = on_connect    
    mqtt_client.on_disconnect = on_disconnect  
    mqtt_client.on_message = on_message 
    mqtt_client.connect(host=mqttHost,port=int(mqttPort)) 
    
    mqtt_client.loop_start()

    #Setup the Async stuff
    #define the stop for the function
    periodic_stop = threading.Event()

    # start up the async method (which will call itself in the future
    periodic(periodic_stop, mqtt_client)

    keepLooping = True

    log.debug("Starting main loop...")
    while keepLooping:
        try:
            time.sleep(MAIN_LOOP_SLEEP)
            #check to see if shutdown received
            if doStop:
                log.debug("Stopping...")
                keepLooping = False
            
            if modbusErrorCount > MODBUS_MAX_ERROR_COUNT:
                log.error("MODBUS not connected, exiting...")
                keepLooping = False
            
            if not mqttConnected:
                if (mqttErrorCount > MQTT_MAX_ERROR_COUNT):
                    log.error("MQTT Error count exceeded, disconnected, exiting...")
                    keepLooping = False

        except KeyboardInterrupt:
            log.error('Interrupted')
            print("Got Keyboard Interuption, exiting...")
            doStop = True
    
    log.debug("Stopping periodic async...")
    periodic_stop.set()

    log.debug("Stopping MQTT loop...")
    mqtt_client.loop_stop()

    log.info("Exiting classic_mqtt")


if __name__ == '__main__':
    run(sys.argv[1:])

