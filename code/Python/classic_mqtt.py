#!/usr/bin/env/python

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from paho.mqtt import client as mqttclient
from collections import OrderedDict
import json
import time
import threading
import logging
import logging.handlers
import os
import sys, getopt

from support.classic_modbusdecoder import getRegisters, getDataDecoder, doDecode
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

classicModbusData         = dict()

wakeCount                 = 0
infoPublished             = True
snoozeCount               = 0
snoozing                  = True

modbusDataGood            = False
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
# configure the client logging
# --------------------------------------------------------------------------- # 
log = logging.getLogger('classic_mqtt')
#handler = logging.FileHandler('./classic_mqtt.log')
handler = logging.handlers.WatchedFileHandler(os.environ.get("LOGFILE", "./classic_mqtt.log"))
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
handler.setFormatter(formatter)
log.addHandler(handler) 
log.setLevel(os.environ.get("LOGLEVEL", "DEBUG"))


# --------------------------------------------------------------------------- # 
# Run the main payload decoder
# --------------------------------------------------------------------------- # 
def getModbusData():

    global modbusDataGood, modbusErrorCount

    try:
        modclient = ModbusClient(classicHost, port=classicPort)
        #Test for succesful connect, if not, log error and mark modbusConnected = False
        modclient.connect()
    except:
        modbusErrorCount += 1
        e = sys.exc_info()[0]
        log.error("MODBUS Error H:{} P:{} e:{}".format(mqttHost, mqttPort, e))
        modbusDataGood = False
        return dict()

    #test by trying to read something
    result = modclient.read_holding_registers(4163, 2,  unit=10)
    if result.isError():
        modbusErrorCount += 1
        modbusDataGood = False
        # close the client
        log.error("MODBUS Connection Error H:{} P:{} count:{}".format(mqttHost, mqttPort, modbusErrorCount))
        modclient.close()
        return dict()

    theData = dict()

    #Read in all the registers at one time
    theData[4100] = getRegisters(theClient=modclient,addr=4100,count=44)
    theData[4360] = getRegisters(theClient=modclient,addr=4360,count=22)
    theData[4163] = getRegisters(theClient=modclient,addr=4163,count=2)
    theData[4209] = getRegisters(theClient=modclient,addr=4209,count=4)
    theData[4243] = getRegisters(theClient=modclient,addr=4243,count=32)
    theData[16386]= getRegisters(theClient=modclient,addr=16386,count=4)

    # close the client
    modclient.close()

    log.debug("Got data from Classic at {}:{}".format(mqttHost,mqttPort))

    modbusErrorCount = 0
    modbusDataGood = True

    #Iterate over them and get the decoded data all into one dict
    decoded = dict()
    for index in theData:
        decoded = {**dict(decoded), **dict(doDecode(index, getDataDecoder(theData[index])))}

    return decoded

# --------------------------------------------------------------------------- # 
# MQTT On Connect function
# --------------------------------------------------------------------------- # 
def on_connect(client, userdata, flags, rc):
    global mqttConnected, mqttErrorCount
    if rc==0:
        mqttConnected = True
        mqttErrorCount = 0
        log.debug("MQTT connected OK Returned code={}".format(rc))
        #subscribe to the commands
        client.subscribe("{}/classic/cmnd/#".format(mqttRoot))

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
        elif msg == "STOP":
            doStop = True
        else:
            log.debug("on_message: Received something else")
            

# --------------------------------------------------------------------------- # 
# MQTT Publish the data
# --------------------------------------------------------------------------- # 
def mqttPublish(client, data, subtopic):
    global mqttRoot, mqttConnected, mqttErrorCount

    topic = "{}/classic/stat/{}".format(mqttRoot, subtopic)
    log.debug(topic)
    
    if not mqttConnected:
        log.error("MQTT not connected, skipping publish")
        mqttErrorCount += 1
        

    try:
        client.publish(topic,data)
    except:
        mqttConnected = False
        mqttErrorCount += 1
        e = sys.exc_info()[0]
        log.error("MQTT Publish Error Topic:{} e:{}".format(topic, e))

# --------------------------------------------------------------------------- # 
# Publish
# --------------------------------------------------------------------------- # 
def publish(client):
    global infoPublished, classicModbusData, modbusDataGood, mqttErrorCount

    if not modbusDataGood:
        log.debug("No modbus data so skipping processing")
        return 

    if (not infoPublished):
        #Check if the Info has been published yet
        mqttPublish(client,encodeClassicData_info(classicModbusData),"info")
        infoPublished = True

    mqttPublish(client,encodeClassicData_readings(classicModbusData),"readings")

# --------------------------------------------------------------------------- # 
# Publish handling Snoozing etc.
# --------------------------------------------------------------------------- # 
def publishReadingsAndInfo(client):
    global snoozing, snoozeCount, infoPublished, wakeCount

    if snoozing:
        if (snoozeCount >= MQTT_SNOOZE_COUNT):
            infoPublished = False
            publish(client)
            snoozeCount = 0
        else:
            snoozeCount += 1
    else:
        publish(client)
        wakeCount += 1
        if wakeCount >= WAKE_COUNT:
            snoozing = True
            wakeCount = 0
    

# --------------------------------------------------------------------------- # 
# Async called to read from MODBUS
# --------------------------------------------------------------------------- # 
def modbus_periodic(modbus_stop):

    global classicModbusData
    if not modbus_stop.is_set():

        #Get the Modbus Data and store it.
        classicModbusData = getModbusData()

        # set myself to be called again in correct number of seconds
        threading.Timer(MODBUS_POLL_RATE, modbus_periodic, [modbus_stop]).start()

# --------------------------------------------------------------------------- # 
# Async called to read publish data to MQTT
# --------------------------------------------------------------------------- # 
def mqtt_publish_periodic(mqtt_stop, client):
    # do something here ...
    if not mqtt_stop.is_set():

        publishReadingsAndInfo(client)
   
        # set myself to be called again in correct number of seconds
        threading.Timer(MQTT_PUBLISH_RATE, mqtt_publish_periodic, [mqtt_stop, client]).start()

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

    #setup the MQTT Client for publishing and subscribing
    mqtt_client = mqttclient.Client(mqttUser+"_mqttclient") 
    mqtt_client.username_pw_set(mqttUser, password=mqttPassword)
    mqtt_client.on_connect = on_connect    
    mqtt_client.on_disconnect = on_disconnect   
    mqtt_client.connect(host=mqttHost,port=int(mqttPort)) 
    
    #Subscribe to the command messages sent to this channel
    mqtt_client.on_message = on_message 
    #mqtt_client.subscribe("{}/classic/cmnd/#".format(mqttRoot))

    #MQTT loop so that messages can be received and reconnects can happen
    mqtt_client.loop_start()

    #Setup the Async stuff
    #define the stop for the function
    modbus_stop = threading.Event()

    # start up the async method (which will call itself in the future
    modbus_periodic(modbus_stop)

    #define the stop for the function
    mqtt_stop = threading.Event()

    # start up the async method (which will call itself in the future
    mqtt_publish_periodic(mqtt_stop, mqtt_client)

    keepLooping = True
    mqttErrorCount = 0

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
                    log.error("MQTT Disconnected, exiting...")
                    keepLooping = False

        except KeyboardInterrupt:
            log.error('Interrupted')
            print("Got Keyboard Interuption, exiting...")
            doStop = True
    
    log.debug("Stopping mqtt async...")
    mqtt_stop.set()
    mqtt_client.loop_stop()

    log.debug("Stopping modbus async...")
    modbus_stop.set()

    log.info("Exiting classic_mqtt")


if __name__ == '__main__':
    run(sys.argv[1:])

