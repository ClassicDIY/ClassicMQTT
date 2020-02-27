#!/usr/bin/env python

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from paho.mqtt import client as mqttclient
from collections import OrderedDict
import json
import time
import threading
import logging
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

classicModbusData         = dict()
snoozeCount               = 0
snoozing                  = True
wakeCount                 = 0
infoPublished             = True
doStop                    = False
classicDataGood           = False
mqttConnected             = False


classicHost               = "ClassicHost"
classicPort               = "502" #15284
mqttHost                  = "127.0.0.1"
mqttPort                  = 1883
mqttRoot                  = "ClassicMQTT"
mqttUser                  = "username"
mqttPassword              = "password"




# --------------------------------------------------------------------------- # 
# configure the client logging
# --------------------------------------------------------------------------- # 
FORMAT = ('%(asctime)-15s %(threadName)-15s'
          ' %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s')
logging.basicConfig(format=FORMAT)
log = logging.getLogger()
log.setLevel(logging.INFO)

# --------------------------------------------------------------------------- # 
# Run the main payload decoder
# --------------------------------------------------------------------------- # 
def getModbusData():

    global classicDataGood

    modclient = ModbusClient(classicHost, port=classicPort)
    #Test for succesful connect, if not, log error and mark modbusConnected = False
    modclient.connect()
    
    #test by trying to read something
    result = modclient.read_holding_registers(4163, 2,  unit=10)
    if result.isError():
        log.error("MDBUS Connection Error H:{} P:{}".format(mqttHost, mqttPort))
        classicDataGood = False
        return dict()

    classicDataGood = True
    theData = dict()

    #Read in all the registers at one time
    theData[4100] = getRegisters(theClient=modclient,addr=4100,count=44)
    theData[4360] = getRegisters(theClient=modclient,addr=4360,count=22)
    theData[4163] = getRegisters(theClient=modclient,addr=4163,count=2)
    theData[4209] = getRegisters(theClient=modclient,addr=4209,count=4)
    theData[4243] = getRegisters(theClient=modclient,addr=4243,count=32)
    #theData[16384]= getRegisters(theClient=modclient,addr=16384,count=12)

    # close the client
    modclient.close()

    #Iterate over them and get the decoded data all into one dict
    decoded = dict()
    for index in theData:
        decoded = {**dict(decoded), **dict(doDecode(index, getDataDecoder(theData[index])))}

    return decoded

def on_connect(client, userdata, flags, rc):
    global mqttConnected
    if rc==0:
        mqttConnected = True
        log.debug("MQTT connected OK Returned code={}".format(rc))
    else:
        mqttConnected = False
        log.error("MQTT Bad connection Returned code={}".format(rc))

def on_disconnect(client, userdata, rc):
    global mqttConnected
    mqttConnected = False

def on_message(client, userdata, message):
        #print("Received message '" + str(message.payload) + "' on topic '"
        #+ message.topic + "' with QoS " + str(message.qos))

        global wakeCount
        global infoPublished
        global snoozing
        global doStop

        log.debug(message.payload)
        msg = message.payload.decode(encoding='UTF-8')
        msg = msg.upper()

        log.debug(msg)

        if msg == "{\"WAKE\"}":
            wakeCount = 0
            infoPublished = False
            snoozing = False
        elif msg == "{\"INFO\"}":
            wakeCount = 0
            infoPublished = False
            snoozing = False
        elif msg == "STOP":
            doStop = True
        else:
            print("Received something else")
            

# --------------------------------------------------------------------------- # 
# Read from the address and return a decoder
# --------------------------------------------------------------------------- # 
def mqttPublish(client, data, subtopic):
    global mqttRoot

    topic = "{}/classic/stat/{}".format(mqttRoot, subtopic)
    log.debug(topic)
    
    if not mqttConnected:
        log.error("MQTT not connected, skipping publish")

    client.publish(topic,data)

def publish(client):
    global infoPublished, classicModbusData, classicDataGood

    if not classicDataGood:
        log.debug("No modbus data so skipping processing")
        return 

    #print(encodeClassicData_info(classicModbusData))
    if (not infoPublished):
        #Check if the Info has been published yet
        mqttPublish(client,encodeClassicData_info(classicModbusData),"info")
        infoPublished = True

    mqttPublish(client,encodeClassicData_readings(classicModbusData),"readings")

def publishReadingsAndInfo(client):
    global snoozing, snoozeCount, infoPublished, wakeCount

    if snoozing:
        if (snoozeCount >= MQTT_SNOOZE_COUNT):
            infoPublished = False
            publish(client)
            snoozeCount = 0
        else:
            snoozeCount = snoozeCount + 1
    else:
        publish(client)
        wakeCount = wakeCount + 1
        if wakeCount >= WAKE_COUNT:
            snoozing = True
            wakeCount = 0
    

def modbus_periodic(modbus_stop):

    global classicModbusData
    if not modbus_stop.is_set():

        #Get the Modbus Data and store it.
        classicModbusData = getModbusData()

        # set myself to be called again in correct number of seconds
        threading.Timer(MODBUS_POLL_RATE, modbus_periodic, [modbus_stop]).start()

def mqtt_publish_periodic(mqtt_stop, client):
    # do something here ...
    if not mqtt_stop.is_set():

        publishReadingsAndInfo(client)
   
        # set myself to be called again in correct number of seconds
        threading.Timer(MQTT_PUBLISH_RATE, mqtt_publish_periodic, [mqtt_stop, client]).start()

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


def run(argv):

    handleArgs(argv)


    global doStop, mqttRoot, mqttConnected

    #setup the MQTT Client for publishing and subscribing
    client = mqttclient.Client(mqttUser+"_mqttclient") #create new instance
    client.username_pw_set(mqttUser, password=mqttPassword)
    client.on_connect = on_connect    
    client.on_disconnect = on_disconnect   
    client.connect(host=mqttHost,port=int(mqttPort)) #connect to broker islandmqtt.eastus.cloudapp.azure.com
    
    #setup command subscription
    client.on_message = on_message 
    client.subscribe("{}/classic/cmnd/#".format(mqttRoot))


    #loop on the receives
    client.loop_start()

    #define the stop for the function
    modbus_stop = threading.Event()

    # start calling f now and every 60 sec thereafter
    modbus_periodic(modbus_stop)

    #define the stop for the function
    mqtt_stop = threading.Event()

    # start calling f now and every 60 sec thereafter
    mqtt_publish_periodic(mqtt_stop, client)

    keepon = True
    mqttDiscCount = 0

    while keepon:
        time.sleep(5)
        #check to see if shutdown received
        if doStop:
            log.debug("Stopping...")
            keepon = False
        elif not mqttConnected:
            if (mqttDiscCount > 300):
                log.error("MQTT Disconnected")
                keepon = False
            else:
                mqttDiscCount = mqttDiscCount + 1
        else:
            mqttDiscCount = 0
    
    modbus_stop.set()
    mqtt_stop.set()
    client.loop_stop()


if __name__ == '__main__':
    run(sys.argv[1:])