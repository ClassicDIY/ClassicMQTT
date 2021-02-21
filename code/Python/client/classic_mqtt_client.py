#!/usr/bin/python3

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
from time import time_ns
from datetime import datetime, timedelta
from classic_client_validate import handleClientArgs


# --------------------------------------------------------------------------- # 
# GLOBALS
# --------------------------------------------------------------------------- # 
MODBUS_MAX_ERROR_COUNT      = 300       #Number of errors on the MODBUS before the tool exits
MQTT_MAX_ERROR_COUNT        = 300       #Number of errors on the MQTT before the tool exits
MAIN_LOOP_SLEEP_SECS        = 5         #Seconds to sleep in the main loop

# --------------------------------------------------------------------------- # 
# Default startup values. Can be over-ridden by command line options.
# --------------------------------------------------------------------------- # 
argumentValues = { \
    'classicName':os.getenv('CLASSIC_NAME', "classic"), \
    'mqttHost':os.getenv('MQTT_HOST', "mosquitto"), \
    'mqttPort':os.getenv('MQTT_PORT', "1883"), \
    'mqttRoot':os.getenv('MQTT_ROOT', "ClassicMQTT"), \
    'mqttUser':os.getenv('MQTT_USER', "ClassicClient"), \
    'mqttPassword':os.getenv('MQTT_PASS', "ClassicClient123"), \
    'file':os.getenv('FILE',"./classic_client_data.txt")}

chargeStateDict = {0: 'Resting',
                   3: 'Absorb',
                   4: 'Bulk MPPT',
                   5: 'Float',
                   6: 'Float MPPT',
                   7: 'Equalize',
                  10: 'Hyper VOC',
                  18: 'Eq MPPT'}

 
# --------------------------------------------------------------------------- # 
# Counters and status variables
# --------------------------------------------------------------------------- # 
mqttConnected               = False
doStop                      = False

mqttErrorCount              = 0
mqttClient                  = None

newMsg = None

# --------------------------------------------------------------------------- # 
# configure the logging
# --------------------------------------------------------------------------- # 
log = logging.getLogger('classic_mqtt_client')
if not log.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler) 
    log.setLevel(os.getenv('LOGLEVEL', "DEBUG"))

# --------------------------------------------------------------------------- # 
# MQTT On Connect function
# --------------------------------------------------------------------------- # 
def on_connect(client, userdata, flags, rc):
    global mqttConnected, mqttErrorCount, mqttClient
    if rc==0:
        log.debug("MQTT connected OK Returned code={}".format(rc))
        #subscribe to the commands
        try:
            topic = "{}{}/stat/readings/#".format(argumentValues['mqttRoot'], argumentValues['classicName'])
            client.subscribe(topic)
            log.debug("Subscribed to {}".format(topic))


            #publish that we are Online
            #will_topic = "{}{}/tele/LWT".format(argumentValues['mqttRoot'], argumentValues['classicName'])
            #mqttClient.publish(will_topic, "Online",  qos=0, retain=False)
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

        global mqttConnected, mqttErrorCount, newMsg

        mqttConnected = True #got a message so we must be up again...
        mqttErrorCount = 0

        #Convert the JSON message to a Python object
        theMessage = json.loads(message.payload.decode(encoding='UTF-8'))
        #log.debug(theMessage)

        #The message should be a "readings" packet, 
        #we only care about the values with -->> next to them.
        #{
        # -->>"BatTemperature":-10.4,
        # "NetAmpHours":1,
        # -->>"ChargeState":4,
        # "InfoFlagsBits":-1308610556,
        # "ReasonForResting":5,
        # "NegativeAmpHours":-11854,
        # -->>"BatVoltage":26.7,
        # "PVVoltage":73.1,
        # "VbattRegSetPTmpComp":30.6,
        # "TotalAmpHours":600,
        # -->>"WhizbangBatCurrent":0.8,
        # "BatCurrent":0.2,
        # "PVCurrent":0.3,
        # "ConnectionState":0,
        # "EnergyToday":0.1,
        # "EqualizeTime":10800,
        # -->>"SOC":97,
        # "Aux1":false,
        # "Aux2":false,
        # "Power":5.0,
        # "FETTemperature":15.6,
        # "PositiveAmpHours":22721,
        # "TotalEnergy":795.9,
        # "FloatTimeTodaySeconds":0,
        # "RemainingAmpHours":583,
        # "AbsorbTime":18000,
        # "ShuntTemperature":-6.0,
        # "PCBTemperature":20.1}

        newMsg = theMessage

# --------------------------------------------------------------------------- # 
# File age check
# --------------------------------------------------------------------------- # 
def is_file_older_than (file, delta): 
    if not os.path.exists(file):
        log.debug("File does not exist, returning True")
        return True
    
    cutoff = datetime.utcnow() - delta
    mtime = datetime.utcfromtimestamp(os.path.getmtime(file))
    if mtime < cutoff:
        log.debug("File is too old, returning True")
        return True

    log.debug("File is recent, returning False")
    return False



# --------------------------------------------------------------------------- # 
# Main
# --------------------------------------------------------------------------- # 
def run(argv):

    global doStop, mqttClient, mqttConnected, mqttErrorCount, newMsg

    log.info("classic_mqtt_client starting up...")

    handleClientArgs(argv, argumentValues)

    #random seed from the OS
    seed(int.from_bytes( os.urandom(4), byteorder="big"))

    mqttErrorCount = 0

    #If there is no file there, or the file is older than 10 minutes
    #write out a message in the file saying that system has not yet received data.
    if is_file_older_than(argumentValues['file'], timedelta(minutes=10)):
        log.info("File is old or not there, writing one out with a message...")
        wr = open(argumentValues['file'], 'w')
        wr.write("No data received as of {}\n".format(datetime.now().strftime("%c")))
        wr.close()

    #setup the MQTT Client for publishing and subscribing
    clientId = argumentValues['mqttUser'] + "_mqttclient_" + str(randint(100, 999))
    log.info("Connecting with clientId=" + clientId)
    mqttClient = mqttclient.Client(clientId) 
    mqttClient.username_pw_set(argumentValues['mqttUser'], password=argumentValues['mqttPassword'])
    mqttClient.on_connect = on_connect    
    mqttClient.on_disconnect = on_disconnect  
    mqttClient.on_message = on_message

    #Set Last Will 
    #will_topic = "{}{}/tele/LWT".format(argumentValues['mqttRoot'], argumentValues['classicName'])
    #mqttClient.will_set(will_topic, payload="Offline", qos=0, retain=False)

    try:
        log.info("Connecting to MQTT {}:{}".format(argumentValues['mqttHost'], argumentValues['mqttPort']))
        mqttClient.connect(host=argumentValues['mqttHost'],port=int(argumentValues['mqttPort'])) 
    except Exception as e:
        log.error("Unable to connect to MQTT, exiting...")
        sys.exit(2)


    mqttClient.loop_start()

    log.debug("Starting main loop...")
    while not doStop:
        try:
            time.sleep(MAIN_LOOP_SLEEP_SECS)

            if not mqttConnected:
                if (mqttErrorCount > MQTT_MAX_ERROR_COUNT):
                    log.error("MQTT Error count exceeded, disconnected, exiting...")
                    doStop = True
            else:
                #Check to see if new data received
                if newMsg != None:
                    currentMsg = newMsg
                    newMsg = None

                    #Get the values we care about
                    # -->>"BatTemperature":-10.4,
                    # -->>"BatVoltage":26.7,
                    # -->>"ChargeState":4,
                    # -->>"WhizbangBatCurrent":0.8,
                    # -->>"SOC":97,

                    batTempC = currentMsg['BatTemperature']
                    batTempF = '{:.1f}'.format((batTempC * 1.8) + 32)
                    batVolts = currentMsg['BatVoltage']
                    batCurrent = currentMsg['WhizbangBatCurrent']
                    chargeState = currentMsg['ChargeState']
                    SOC = currentMsg['SOC']

                    #write out the file...
                    log.debug("Writing the values out to the file.")
                    log.debug("SOC {}%".format(SOC))
                    log.debug("Battery is {} V".format(batVolts))
                    log.debug("Battery Current is {}A".format(batCurrent))
                    log.debug("Battery Temp is {}C {}F".format(batTempC, batTempF))

                    if chargeState in chargeStateDict:
                        chargeStateStr = chargeStateDict[chargeState]
                    else:
                        chargeStateStr = "Unknown Code " + chargeState

                    dt_string = datetime.now().strftime("%-m/%-d/%-Y %H:%M:%S")

                    wr = open(argumentValues['file'], 'w')
                    wr.write("Battery SOC: {}%\n".format(SOC))
                    wr.write("Volts: {}V\n".format(batVolts))
                    wr.write("Charge State: {}\n".format(chargeStateStr))
                    wr.write("Current: {}A\n".format(batCurrent))
                    wr.write("Battery Temp: {}C/{}F\n".format(batTempC,batTempF))
                    wr.write("as of {}\n".format(dt_string))
                    wr.close()

        except KeyboardInterrupt:
            log.error("Got Keyboard Interuption, exiting...")
            doStop = True
        except Exception as e:
            log.error("Caught other exception...")
            log.exception(e, exc_info=True)
    
    log.info("Exited the main loop, stopping other loops")

    log.info("Stopping MQTT loop...")
    mqttClient.loop_stop()

    log.info("Exiting classic_mqtt_client")

if __name__ == '__main__':
    run(sys.argv[1:])
