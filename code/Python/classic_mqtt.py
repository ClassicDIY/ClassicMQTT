#!/usr/bin/python3

try:
    from pymodbus.client import ModbusTcpClient as ModbusClient  # pymodbus 3
except ImportError:
    from pymodbus.client.sync import ModbusTcpClient as ModbusClient  # pymodbus 2
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
MIN_WAKE_RATE               = 2         #in seconds
DEFAULT_WAKE_RATE           = 5         #in seconds
MIN_WAKE_PUBLISHES          = 15        #minimum number of publishes before snoozing this * wake_rate = time awake
DEFAULT_WAKE_PUBLISHES      = 60        #default number of publishes before switching to snooze

MAX_SNOOZE_RATE             = 4*60*60   #in seconds (4 hours)
MIN_SNOOZE_RATE             = 1*60      #in seconds (1 minute)
DEFAULT_SNOOZE_RATE         = 5*60      #in seconds (5 minutes)

MODBUS_MAX_ERROR_COUNT      = 300       #Number of errors on the MODBUS before the tool exits
MQTT_MAX_ERROR_COUNT        = 300       #Number of errors on the MQTT before the tool exits
MAIN_LOOP_SLEEP_SECS        = 5         #Seconds to sleep in the main loop

HA_ENABLED                  = False     #Home-Assistant Auto Discovery

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
    'awakePublishLimit':int(os.getenv('AWAKE_PUBLISH_LIMIT', str(DEFAULT_WAKE_PUBLISHES))), \
    'homeassistant':os.getenv('HA_ENABLED', str(HA_ENABLED)) \
    }

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
homeassistantEnabled        = False

mqttDeviceModel             = 'Classic'
mqttDeviceFirmware          = ''
mqttLastSOCicon             = ''
mqttLastCSicon              = ''

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
    global mqttConnected, mqttErrorCount, mqttClient, mqttDeviceModel
    if rc==0:
        log.debug("MQTT connected OK Returned code={}".format(rc))
        # re-initiate HA-autodiscovery
        infoPublished = False
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
                infoPublished = False 
                modeAwake = True
                log.debug("StayAwake received, setting stayAwake to {}".format(stayAwake))
            
            elif "wakePublishRate" in theMessage:
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

def mqttHApublish( sensor, name, units, icon, inforead, vtemplate, data ):
    #publisch HA autodiscovery for 1 sensor/diagnostic
    global mqttClient, argumentValues, mqttDeviceModel, mqttDeviceFirmware
    #
    HA_root = argumentValues['mqttRoot']
    HA_name = argumentValues['classicName']
    HA_device = '"force_update": "true", "device": {{ "identifiers": ["{}"],"name": "{}","manufacturer": "MidNite-Solar","model": "{}", "sw_version": "{}"}}'.format( HA_name, HA_name, mqttDeviceModel, mqttDeviceFirmware )
    # Vtemplate
    HA_vtemplate = '{{{{value_json.{0}}}}}'.format(sensor)
    if vtemplate != '':
        HA_vtemplate = vtemplate
    # Units
    HA_units = units
    if units == 'C':
        HA_icon = '"icon": "mdi:thermometer", '
        if icon != '':
            HA_icon = icon
            icon = ''
        HA_units = '"unit_of_meas": "°C", '+HA_icon+'"device_class": "temperature", "state_class": "measurement", '
    if units == 'A':
        HA_units = '"unit_of_meas": "A", "device_class": "power", "state_class": "measurement", '
    if units == 'V':
        HA_units = '"unit_of_meas": "V", "device_class": "power", "state_class": "measurement", '
    if units == 'W':
        HA_units = '"unit_of_meas": "W", "device_class": "power", "state_class": "measurement", '
    if units == 'kWh':
        HA_units = '"unit_of_meas": "kWh", "device_class": "power", "state_class": "measurement", '
    if units == '%':
        HA_icon = '' # '"icon": "mdi:battery", '
        if icon != '':
            HA_icon = icon
            icon = ''
        HA_units = '"unit_of_meas": "%", '+HA_icon+'"state_class": "measurement", '
    if units == 's':
        HA_icon = '"icon": "mdi:clock", '
        if icon != '':
            HA_icon = icon
            icon = ''
        HA_units = '"unit_of_meas": "s", '+HA_icon+'"state_class": "measurement", '
    if units == 'Ah':
        HA_units = '"unit_of_meas": "Ah", "device_class": "power", "state_class": "measurement", '
    #
    HA_topic = "homeassistant/sensor/{}/{}/config".format(HA_name, sensor)
    HA_msg = '{{"~": "{0}", "unique_id": "{0}-{1}", "object_id": "{0}-{1}", "name": "{2}", {3}{4}"state_topic": "{5}{0}/stat/{6}", "value_template": "{8}", {7}}}'.format(
    HA_name, sensor, name, icon, HA_units, HA_root, inforead, HA_device, HA_vtemplate )
    #	0		1		2	3		4		5			6			7			8
    #log.debug( "publish: {}".format(HA_msg) )
    mqttClient.publish(HA_topic, HA_msg,  qos=0, retain=False)
    #

def mqttHA_autodiscovery( data ):
    # publisch HA autodiscovery
    global mqttClient, argumentValues, mqttDeviceModel, mqttDeviceFirmware
    #
    log.debug("mqttHA_autodiscovery")
    mqttDeviceModel = "Classic {}V (rev {})".format(data["Type"],data["PCB"])
    mqttDeviceFirmware = "{:04n}{:02n}{:02n}.app.{}.net.{}".format(data["Year"],data["Month"],data["Day"],data['app_rev'],data['net_rev'])
    #
    # Device info
    mqttHApublish( 'model', 'device Model', '"entity_category": "diagnostic", ', '"icon": "mdi:teddy-bear", ', 'info', '', data )
    mqttHApublish( 'deviceName', 'device Name', '"entity_category": "diagnostic", ', '"icon": "mdi:home-analytics", ', 'info', '', data )
    mqttHApublish( 'deviceType', 'device Type', '"entity_category": "diagnostic", ', '"icon": "mdi:format-list-bulleted-type", ', 'info', '', data )
    mqttHApublish( 'macAddress', 'MAC Address', '"entity_category": "diagnostic", ', '"icon": "mdi:console-network", ', 'info', '', data )
    mqttHApublish( 'IP', 'IP Address', '"entity_category": "diagnostic", ', '"icon": "mdi:ip-network", ', 'info', '', data )
    mqttHApublish( 'nominalBatteryVoltage', 'nominal Battery Voltage', '"entity_category": "diagnostic", "unit_of_meas": "V", ', '"icon": "mdi:battery-charging", ', 'info', '', data )
    # Measurements
    mqttHApublish( 'BatTemperature', 'Temperature Battery', 'C', '', 'readings', '', data )
    mqttHApublish( 'PCBTemperature', 'Temperature PCB', 'C', '', 'readings', '', data )
    mqttHApublish( 'FETTemperature', 'Temperature FET', 'C', '', 'readings', '', data )
    mqttHApublish( 'ShuntTemperature', 'Temperature Shunt', 'C', '', 'readings', '', data )
    mqttHApublish( 'PVCurrent', 'PV Current', 'A', '"icon": "mdi:solar-panel", ', 'readings', '', data )
    mqttHApublish( 'Power', 'PV Power', 'W', '"icon": "mdi:solar-panel", ', 'readings', '', data )
    mqttHApublish( 'PVVoltage', 'PV Voltage', 'V', '"icon": "mdi:solar-panel", ', 'readings', '', data )
    mqttHApublish( 'BatVoltage', 'Battery Voltage', 'V', '', 'readings', '', data )
    mqttHApublish( 'BatCurrent', 'Battery Current', 'A', '', 'readings', '', data )
    mqttHApublish( 'WhizbangBatCurrent', 'Battery Current Whizbang', 'A', '', 'readings', '', data )
    mqttHApublish( 'SOC', 'Charge SOC', '"unit_of_meas": "%", "state_class": "measurement", ', '"icon": "'+data['SOCicon']+'", ', 'readings', '', data )
    mqttHApublish( 'RemainingAmpHours', 'Amp Hours Remaining', 'Ah', '', 'readings', '', data )
    mqttHApublish( 'TotalAmpHours', 'Amp Hours Total', 'Ah', '', 'readings', '', data )
    mqttHApublish( 'NetAmpHours', 'Amp Hours Netto', 'Ah', '', 'readings', '', data )
    mqttHApublish( 'EnergyToday', 'Energy Today', 'kWh', '"icon": "mdi:calendar-today", ', 'readings', '', data )
    mqttHApublish( 'TotalEnergy', 'Energy Total', 'kWh', '"icon": "mdi:home-lightning-bolt-outline", ', 'readings', '', data )
    mqttHApublish( 'currentTime', 'Current Time', '"state_class": "measurement", ', '"icon": "mdi:calendar-clock", ', 'readings', '', data )
    mqttHApublish( 'ChargeState', 'Charge State', '', '"icon": "'+data['ChargeStateIcon']+'", ', 'readings', '', data )
    mqttHApublish( 'ChargeStateText', 'Charge State Text', '', '"icon": "'+data['ChargeStateIcon']+'", ', 'readings', '', data )
    #mqttHApublish( 'ChargeStateText', 'Charge State Text', '', '"icon": "'+data['ChargeStateIcon']+'", ', 'readings', '{{ {0: \'Resting\',3: \'Absorb\',4: \'Bulk MPPT\',5: \'Float\',6: \'Float MPPT\',7: \'Equalize\',10: \'HyperVOC\',18: \'Equalize MPPT\'}[value_json.ChargeState]}}', data )
    mqttHApublish( 'FloatTimeTodaySeconds', 'Today Float Time', 's', '', 'readings', '', data )
    mqttHApublish( 'AbsorbTime', 'Today Absorb Time', 's', '', 'readings', '', data )
    mqttHApublish( 'EqualizeTime', 'Today Equalize Time', 's', '', 'readings', '', data )
    mqttHApublish( 'ReasonForResting', 'Reason For Resting', '"state_class": "measurement", ', '', 'readings', '', data )
    mqttHApublish( 'ReasonForRestingText', 'Reason Text', '"state_class": "measurement", ', '', 'readings', '', data )
# {
#     "appVersion": 1849,
#     "deviceName": "CLASSIC\u0000", < 1 char too much / stop on 0
#     "buildDate": "Monday, April 21, 2014",
#     "deviceType": "Classic",
#     "endingAmps": 4,
#     "hasWhizbang": true,
#     "lastVOC": 39.6,
#     "model": "Classic 150V (rev 4)",
#     "mpptMode": 9,
#     "netVersion": 1839,
#     "nominalBatteryVoltage": 12,
#     "unitID": -1966686451,
#     "macAddress": "60:1D:0F:00:36:80"
# }
# {
#     "BatTemperature": 8.1,
#     "NetAmpHours": -172,
#     "ChargeState": 4,
#     "InfoFlagsBits": -1577046016,
#     "ReasonForResting": 5,
#     "NegativeAmpHours": -59292,
#     "BatVoltage": 13.4,
#     "PVVoltage": 32.7,
#     "VbattRegSetPTmpComp": 15.1,
#     "TotalAmpHours": 908,
#     "WhizbangBatCurrent": 12,
#     "BatCurrent": 17.5,
#     "PVCurrent": 7,
#     "ConnectionState": 0,
#     "EnergyToday": 0.2,
#     "EqualizeTime": 14400,
#     "SOC": 78,
#     "Aux1": false,
#     "Aux2": false,
#     "Power": 233,
#     "FETTemperature": 40.4,
#     "PositiveAmpHours": 438335,
#     "TotalEnergy": 2982.7,
#     "FloatTimeTodaySeconds": 0,
#     "RemainingAmpHours": 714,
#     "AbsorbTime": 18000,
#     "ShuntTemperature": 10,
#     "PCBTemperature": 30.4
# }       
    
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

    global mqttClient, modbusErrorCount, infoPublished, mqttErrorCount, currentPollRate, mqttLastSOCicon, mqttLastCSicon, homeassistantEnabled

    if not modbus_stop.is_set():
        #Get the current time as a float of seconds.
        beforeTime = time_ns() /  1000000000.0

        #log.debug("in Periodic")
        try:
            if timeToPublish() and mqttConnected:
                log.debug("Call getModbusData" )
                data = {}
                #Get the Modbus Data and store it.
                data = getModbusData(modeAwake, argumentValues['classicHost'], argumentValues['classicPort'])
                if data: # got data
                    #
                    modbusErrorCount = 0
                    if (not infoPublished): #Check if the Info has been published yet
                        #
                        if ( homeassistantEnabled is True): #Check if HA_enabled is true
                            mqttHA_autodiscovery( data )
                            # wait 1 second for HA to receive and create device
                            time.sleep(1)
                            log.debug("Done mqttHAautodiscovery" )
                            #
                        if mqttPublish(mqttClient,encodeClassicData_info(data),"info"):
                            infoPublished = True
                            time.sleep(1)
                        else:
                            mqttErrorCount += 1
                        #
                    if mqttPublish(mqttClient,encodeClassicData_readings(data),"readings"):
                        #
                        if ( homeassistantEnabled  is True): #Check if HA_enabled is true
                            # re-send ChargeState because of icon
                            if mqttLastCSicon != data["ChargeStateIcon"]:
                                mqttLastCSicon = data["ChargeStateIcon"]
                                log.debug("Call CS mqttHApublish {}".format(mqttLastCSicon) )
                                mqttHApublish( 'ChargeState', 'Charge State', '', '"icon": "'+ data["ChargeStateIcon"] + '", ', 'readings', '', data )
                                mqttHApublish( 'ChargeStateText', 'Charge State Text', '', '"icon": "'+data['ChargeStateIcon']+'", ', 'readings', '{{ {0: \'Resting\',3: \'Absorb\',4: \'Bulk MPPT\',5: \'Float\',6: \'Float MPPT\',7: \'Equalize\',10: \'HyperVOC\',18: \'Equalize MPPT\'}[value_json.ChargeState]}}', data )
                            # re-send SOC because of icon
                            if mqttLastSOCicon != data["SOCicon"]:
                                mqttLastSOCicon = data["SOCicon"]
                                log.debug("Call SOC mqttHApublish {}".format(mqttLastSOCicon) )
                                mqttHApublish( 'SOC', 'Charge SOC', '"unit_of_meas": "%", "state_class": "measurement", ', '"icon": "'+ data["SOCicon"] + '", ', 'readings', '', data )
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

    global doStop, mqttClient, awakePublishCycles, snoozePublishCycles, currentPollRate, snoozeCycleLimit, mqttLastSOCicon, mqttLastCSicon, homeassistantEnabled

    log.info("classic_mqtt starting up...")

    handleArgs(argv, argumentValues)

    snoozeCycleLimit = round(argumentValues['snoozePublishRate']/argumentValues['awakePublishRate'])
    log.debug("snoozeCycleLimit: {}".format(snoozeCycleLimit))

    #Make it publish right away
    awakePublishCycles = argumentValues['awakePublishRate']
    snoozePublishCycles =  argumentValues['snoozePublishRate']

    currentPollRate = argumentValues['awakePublishRate']

    homeassistantEnabled = argumentValues['homeassistant']

    #random seed from the OS
    seed(int.from_bytes( os.urandom(4), byteorder="big"))

    mqttErrorCount = 0

    #setup the MQTT Client for publishing and subscribing
    clientId = argumentValues['mqttUser'] + "_mqttclient_" + str(randint(100, 999))
    log.info("Connecting with clientId=" + clientId)
    mqttClient = mqttclient.Client(mqttclient.CallbackAPIVersion.VERSION1, clientId)
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