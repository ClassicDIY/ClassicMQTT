#!/usr/bin/env python

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from paho.mqtt import client as mqttclient
from collections import OrderedDict
import json
import time
import threading

from classic_modbusdecoder import getRegisters, getDataDecoder, doDecode
from classic_jsonencoder import encodeClassicData_readings, encodeClassicData_info

import classic_globals as g

# --------------------------------------------------------------------------- # 
# configure the client logging
# --------------------------------------------------------------------------- # 

import logging
FORMAT = ('%(asctime)-15s %(threadName)-15s'
          ' %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s')
logging.basicConfig(format=FORMAT)
log = logging.getLogger()
log.setLevel(logging.INFO)

# --------------------------------------------------------------------------- # 
# Run the main payload decoder
# --------------------------------------------------------------------------- # 
def getModbusData():
    # ----------------------------------------------------------------------- #
    # We are going to use a simple client to send our requests
    # ----------------------------------------------------------------------- #
    modclient = ModbusClient('0.tcp.ngrok.io', port=15284)
    modclient.connect()

    theData = dict()

    #Read in all the registers at one time
    theData[4100] = getRegisters(theClient=modclient,addr=4100,count=44)
    theData[4360] = getRegisters(theClient=modclient,addr=4360,count=22)
    theData[4163] = getRegisters(theClient=modclient,addr=4163,count=2)
    theData[4209] = getRegisters(theClient=modclient,addr=4209,count=4)
    theData[4243] = getRegisters(theClient=modclient,addr=4243,count=32)
    #theData[16384]= getRegisters(theClient=modclient,addr=16384,count=12)

    # ----------------------------------------------------------------------- #
    # close the client
    # ----------------------------------------------------------------------- #
    modclient.close()

    #Iterate over them and get the decoded data all into one dict
    decoded = dict()
    for index in theData:
        decoded = {**dict(decoded), **dict(doDecode(index, getDataDecoder(theData[index])))}

    return decoded

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print("MQTT connected OK Returned code=",rc)
    else:
        print("MQTT Bad connection Returned code=",rc)


def on_message(client, userdata, message):
        #print("Received message '" + str(message.payload) + "' on topic '"
        #+ message.topic + "' with QoS " + str(message.qos))

        print(message.payload)
        msg = message.payload.decode(encoding='UTF-8')
        msg = msg.upper()

        print(msg)

        if msg == "{\"WAKE\"}":
            g.wakeCount = 0
            g.infoPublished = False
            g.snoozing = False
        elif msg == "{\"INFO\"}":
            g.wakeCount = 0
            g.infoPublished = False
            g.snoozing = False
        elif msg == "STOP":
            g.doStop = True
        else:
            print("Received something else")
            

# --------------------------------------------------------------------------- # 
# Read from the address and return a decoder
# --------------------------------------------------------------------------- # 
def mqttPublish(client, data, subtopic):

    topic = "{}/classic/stat/{}".format(g.mqttRoot, subtopic)
    print(topic)
    client.publish(topic,data)


def publish(client):
    #print(encodeClassicData_info(g.classicModbusData))
    if (not g.infoPublished):
        #Check if the Info has been published yet
        mqttPublish(client,encodeClassicData_info(g.classicModbusData),"info")
        g.infoPublished = True

    mqttPublish(client,encodeClassicData_readings(g.classicModbusData),"readings")

def publishReadingsAndInfo(client):
    if g.snoozing:
        if (g.snoozeCount >= g.MQTT_SNOOZE_COUNT):
            g.infoPublished = False
            publish(client)
            g.snoozeCount = 0
        else:
            g.snoozeCount = g.snoozeCount + 1
    else:
        publish(client)
        g.wakeCount = g.wakeCount + 1
        if g.wakeCount >= g.WAKE_COUNT:
            g.snoozing = True
            g.wakeCount = 0
    

def modbus_periodic(modbus_stop):
    # do something here ...
    if not modbus_stop.is_set():

        #Get the Modbus Data and store it.
        g.classicModbusData = getModbusData()

        # set myself to be called again in correct number of seconds
        threading.Timer(g.MODBUS_POLL_RATE, modbus_periodic, [modbus_stop]).start()

def mqtt_publish_periodic(mqtt_stop, client):
    # do something here ...
    if not mqtt_stop.is_set():

        publishReadingsAndInfo(client)
   
        # set myself to be called again in correct number of seconds
        threading.Timer(g.MQTT_PUBLISH_RATE, mqtt_publish_periodic, [mqtt_stop, client]).start()


def run():

    #setup the MQTT Client for publishing and subscribing
    broker_address="islandmqtt.eastus.cloudapp.azure.com"     
    client = mqttclient.Client("Classic") #create new instance
    client.username_pw_set("glaserisland", password="R@staman1312")
    
    client.on_connect = on_connect    
    client.connect(broker_address) #connect to broker
    
    #setup command subscription
    client.on_message = on_message 
    client.subscribe("{}/classic/cmnd/#".format(g.mqttRoot))
    #print("{}/classic/cmnd/#".format(g.ROOT_MQTT))


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
    while keepon:
        time.sleep(1)
        #check to see if shutdown received
        if g.doStop:
            keepon = False

    
    modbus_stop.set()
    mqtt_stop.set()
    client.loop_stop()


if __name__ == '__main__':
    run()