#!/usr/bin/env python

# --------------------------------------------------------------------------- # 
# Handle the modbus data from the Classic. 
# The only methon called out of this is getModbusData
# This opens the client to the Classic, gets the data and closes it. It does not
# keep the link open to the Classic.
# --------------------------------------------------------------------------- # 

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
try:
    from pymodbus.client import ModbusTcpClient as ModbusClient  # pymodbus 3
    MODBUS_VERSION = 3
except ImportError:
    from pymodbus.client.sync import ModbusTcpClient as ModbusClient  # pymodbus 2
    MODBUS_VERSION = 2
from collections import OrderedDict
import logging
import sys

log = logging.getLogger('classic_mqtt')

# --------------------------------------------------------------------------- # 
# Read from the address and return the registers
# --------------------------------------------------------------------------- # 
def getRegisters(theClient, addr, count):
    try:
        if MODBUS_VERSION == 2:
            result = theClient.read_holding_registers(addr, count, unit=10)
        else:
            result = theClient.read_holding_registers(addr, count, slave=10)
        if result.function_code >= 0x80:
            log.error("error getting {} for {} bytes".format(addr, count))
            return {}
    except:
        log.error("Error getting {} for {} bytes".format(addr, count))
        return {}

    return result.registers


# --------------------------------------------------------------------------- # 
# Return a decoder for the passed in registers
# --------------------------------------------------------------------------- # 
def getDataDecoder(registers):
    if MODBUS_VERSION == 2:
        return BinaryPayloadDecoder.fromRegisters(
            registers,
            byteorder=Endian.Big,
            wordorder=Endian.Little)
    else:
        return BinaryPayloadDecoder.fromRegisters(
            registers,
            byteorder=Endian.BIG,
            wordorder=Endian.LITTLE)

# --------------------------------------------------------------------------- # 
# Based on the address, return the decoded OrderedDict
# --------------------------------------------------------------------------- # 
def doDecode(addr, decoder):
    if (addr == 4100 ):
        decoded = OrderedDict([
            ('PCB', decoder.decode_8bit_uint()),                       #4101 MSB
            ('Type', decoder.decode_8bit_uint()),                      #4101 LSB
            ('Year', decoder.decode_16bit_uint()),                     #4102
            ('Month', decoder.decode_8bit_uint()),                     #4103 MSB
            ('Day', decoder.decode_8bit_uint()),                       #4103 LSB
            ('InfoFlagBits3', decoder.decode_16bit_uint()),            #4104
            ('ignore', decoder.skip_bytes(2)),                         #4105 Reserved
            ('mac_1', decoder.decode_8bit_uint()),                     #4106 MSB  
            ('mac_0', decoder.decode_8bit_uint()),                     #4106 LSB
            ('mac_3', decoder.decode_8bit_uint()),                     #4107 MSB
            ('mac_2', decoder.decode_8bit_uint()),                     #4107 LSB
            ('mac_5', decoder.decode_8bit_uint()),                     #4108 MSB
            ('mac_4', decoder.decode_8bit_uint()),                     #4108 LSB
            ('ignore2', decoder.skip_bytes(4)),                        #4109, 4110
            ('unitID', decoder.decode_32bit_uint()),                   #4111
            ('StatusRoll', decoder.decode_16bit_uint()),               #4113
            ('RsetTmms', decoder.decode_16bit_uint()),                 #4114
            ('BatVoltage', decoder.decode_16bit_int()/10.0),           #4115
            ('PVVoltage', decoder.decode_16bit_uint()/10.0),           #4116
            ('BatCurrent', decoder.decode_16bit_uint()/10.0),          #4117
            ('EnergyToday', decoder.decode_16bit_uint()/10.0),         #4118
            ('Power', decoder.decode_16bit_uint()/1.0),                #4119
            ('ChargeStage', decoder.decode_8bit_uint()),               #4120 MSB
            ('State', decoder.decode_8bit_uint()),                     #4120 LSB
            ('PVCurrent', decoder.decode_16bit_uint()/10.0),           #4121
            ('lastVOC', decoder.decode_16bit_uint()/10.0),             #4122
            ('HighestVinputLog', decoder.decode_16bit_uint()),         #4123
            ('MatchPointShadow', decoder.decode_16bit_uint()),         #4124
            ('AmpHours', decoder.decode_16bit_uint()),                 #4125
            ('TotalEnergy', decoder.decode_32bit_uint()/10.0),         #4126, 4127
            ('LifetimeAmpHours', decoder.decode_32bit_uint()),         #4128, 4129
            ('InfoFlagsBits', decoder.decode_32bit_uint()),            #4130, 31
            ('BatTemperature', decoder.decode_16bit_int()/10.0),       #4132
            ('FETTemperature', decoder.decode_16bit_int()/10.0),       #4133
            ('PCBTemperature', decoder.decode_16bit_int()/10.0),       #4134
            ('NiteMinutesNoPwr', decoder.decode_16bit_uint()),         #4135
            ('MinuteLogIntervalSec', decoder.decode_16bit_uint()),     #4136
            ('modbus_port_register', decoder.decode_16bit_uint()),     #4137
            ('FloatTimeTodaySeconds', decoder.decode_16bit_uint()),    #4138
            ('AbsorbTime', decoder.decode_16bit_uint()),               #4139
            ('reserved1', decoder.decode_16bit_uint()),                #4140
            ('PWM_ReadOnly', decoder.decode_16bit_uint()),             #4141
            ('Reason_For_Reset', decoder.decode_16bit_uint()),         #4142
            ('EqualizeTime', decoder.decode_16bit_uint()),             #4143
        ])
    elif (addr == 4360):
        decoded = OrderedDict([
            ('WbangJrCmdS', decoder.decode_16bit_uint()),                   #4361
            ('WizBangJrRawCurrent', decoder.decode_16bit_int()),            #4362
            ('skip', decoder.skip_bytes(4)),                                #4363,4364
            ('WbJrAmpHourPOSitive', decoder.decode_32bit_uint()),           #4365,4366
            ('WbJrAmpHourNEGative', decoder.decode_32bit_int()),            #4367,4368
            ('WbJrAmpHourNET', decoder.decode_32bit_int()),                 #4369,4370
            ('WhizbangBatCurrent', decoder.decode_16bit_int()/10.0),        #4371
            ('WizBangCRC', decoder.decode_8bit_int()),                      #4372 MSB
            ('ShuntTemperature', decoder.decode_8bit_int() - 50.0),         #4372 LSB
            ('SOC', decoder.decode_16bit_uint()),                           #4373
            ('skip2', decoder.skip_bytes(6)),                               #4374,75, 76
            ('RemainingAmpHours', decoder.decode_16bit_uint()),             #4377
            ('skip3', decoder.skip_bytes(6)),                               #4378,79,80
            ('TotalAmpHours', decoder.decode_16bit_uint()),                 #4381
        ])
    elif (addr == 4163):
        decoded = OrderedDict([
            ('MPPTMode', decoder.decode_16bit_uint()),                      #4164
            ('Aux1and2Function', decoder.decode_16bit_int()),               #4165
        ])
    elif (addr == 4209):
        decoded = OrderedDict([
            ('Name0', decoder.decode_8bit_uint()),                      #4210-MSB
            ('Name1', decoder.decode_8bit_uint()),                      #4210-LSB
            ('Name2', decoder.decode_8bit_uint()),                      #4211-MSB
            ('Name3', decoder.decode_8bit_uint()),                      #4211-LSB
            ('Name4', decoder.decode_8bit_uint()),                      #4212-MSB
            ('Name5', decoder.decode_8bit_uint()),                      #4212-LSB
            ('Name6', decoder.decode_8bit_uint()),                      #4213-MSB
            ('Name7', decoder.decode_8bit_uint()),                      #4213-LSB
        ])
    elif (addr == 4213):
        decoded = OrderedDict([
            ('CTIME0', decoder.decode_32bit_uint()),                    #4214+#4215
            ('CTIME1', decoder.decode_32bit_uint()),                    #4216+#4217
            ('CTIME2', decoder.decode_32bit_uint()),                    #4218+#4219
        ])
    elif (addr == 4243):
        decoded = OrderedDict([
            ('VbattRegSetPTmpComp', decoder.decode_16bit_int()/10.0),      #4244
            ('nominalBatteryVoltage', decoder.decode_16bit_uint()),          #4245
            ('endingAmps', decoder.decode_16bit_int()/10.0),               #4246
            ('skip', decoder.skip_bytes(56)),                                #4247-4274
            ('ReasonForResting', decoder.decode_16bit_uint()),               #4275
        ])
    elif (addr == 16386):
        decoded = OrderedDict([
            ('app_rev', decoder.decode_32bit_uint()),                     #16387, 16388
            ('net_rev', decoder.decode_32bit_uint()),                     #16387, 16388
        ])

    return decoded

# --------------------------------------------------------------------------- # 
# Get the data from the Classic. 
# Open the cleint, read in the register, close the client, decode the data, 
# combine it and return it 
# --------------------------------------------------------------------------- # 

modbusClient = None
isConnected = False

def getModbusData(modeAwake, classicHost, classicPort):
    
    global isConnected, modbusClient

    try:
        if not isConnected:
            log.debug("Opening the modbus Connection")
            if modbusClient is None:
                modbusClient = ModbusClient(host=classicHost, port=classicPort)

            #Test for successful connect, if not, log error and mark modbusConnected = False
            modbusClient.connect()

            if MODBUS_VERSION == 2:
                result = modbusClient.read_holding_registers(4163, 2, unit=10)
            else:
                result = modbusClient.read_holding_registers(4163, 2, slave=10)

            if result.isError():
                # close the client
                log.error("MODBUS isError H:{} P:{}".format(classicHost, classicPort))
                modbusClient.close()
                isConnected = False
                return {}

            isConnected = True

        theData = {}
        #Read in all the registers at one time
        theData[4100] = getRegisters(theClient=modbusClient,addr=4100,count=44)
        theData[4360] = getRegisters(theClient=modbusClient,addr=4360,count=22)
        theData[4163] = getRegisters(theClient=modbusClient,addr=4163,count=2)
        theData[4209] = getRegisters(theClient=modbusClient,addr=4209,count=4)
        theData[4213] = getRegisters(theClient=modbusClient,addr=4213,count=6)
        theData[4243] = getRegisters(theClient=modbusClient,addr=4243,count=32)
        theData[16386]= getRegisters(theClient=modbusClient,addr=16386,count=4)
        
        #If we are snoozing, then give up the connection
        #log.debug("modeAwake:{}".format(modeAwake))
        if not modeAwake :
            log.debug("Closing the modbus Connection, we are in Snooze mode")
            modbusClient.close()
            isConnected = False

    except: # Catch all modbus excpetions
        e = sys.exc_info()[0]
        log.error("MODBUS Error H:{} P:{} e:{}".format(classicHost, classicPort, e))
        try:
            modbusClient.close()
            isConnected = False

        except:
            log.error("MODBUS Error on close H:{} P:{}".format(classicHost, classicPort))

        return {}

    log.debug("Got data from Classic at {}:{}".format(classicHost,classicPort))

    #Iterate over them and get the decoded data all into one dict
    decoded = {}
    for index in theData:
        decoded = {**dict(decoded), **dict(doDecode(index, getDataDecoder(theData[index])))}

    # Device type 251 is different
    if decoded['Type'] == 251:
        decoded['Type'] = '250 KS'

    # IP number
    decoded['IP'] = classicHost

    # Charge State icon
    decoded['ChargeStateIcon'] = 'mdi:music-rest-whole'
    if decoded['ChargeStage'] == 3 or decoded['ChargeStage'] == 4:
        decoded['ChargeStateIcon'] = 'mdi:battery-charging'
    elif decoded['ChargeStage'] == 5 or decoded['ChargeStage'] == 6:
        decoded['ChargeStateIcon'] = 'mdi:format-float-center'
    elif decoded['ChargeStage'] >= 7:
        decoded['ChargeStateIcon'] = 'mdi:approximately-equal'
    #
    chrg_stt_txt_arr = {
        0: 'Resting',
        3: 'Absorb',
        4: 'Bulk MPPT',
        5: 'Float',
        6: 'Float MPPT',
        7: 'Equalize',
        10: 'HyperVOC',
        18: 'Equalize MPPT',
        }
    decoded['ChargeStateText'] = chrg_stt_txt_arr[decoded['ChargeStage']]

    # SOC icon
    SOCicon = "mdi:battery-"
    if decoded["ChargeStage"] == 3 or decoded["ChargeStage"] == 4:
        SOCicon = SOCicon + "charging-"
    SOCicon = SOCicon + str( int( int(decoded["SOC"]) / 10 ) ) + "0"
    if SOCicon == "mdi:battery-100":
        SOCicon = "mdi:battery"
    decoded["SOCicon"] = SOCicon
    # Rest reason
    rest_reason_arr = {
        1: "Anti-Click. Not enough power available (Wake Up)",
        2: " Insane Ibatt Measurement (Wake Up)",
        3: " Negative Current (load on PV input ?) (Wake Up)",
        4: " PV Input Voltage lower than Battery V (Vreg state)",
        5: " Too low of power out and Vbatt below set point for > 90 seconds",
        6: " FET temperature too high (Cover is on maybe?)",
        7: " Ground Fault Detected",
        8: " Arc Fault Detected",
        9: " Too much negative current while operating (backfeed from battery out of PV input)",
        10: "Battery is less than 8.0 Volts",
        11: "PV input is available but V is rising too slowly. Low Light or bad connection(Solar mode)",
        12: "Voc has gone down from last Voc or low light. Re-check (Solar mode)",
        13: "Voc has gone up from last Voc enough to be suspicious. Re-check (Solar mode)",
        14: "PV input is available but V is rising too slowly. Low Light or bad connection(Solar mode)",
        15: "Voc has gone down from last Voc or low light. Re-check (Solar mode)",
        16: "Mppt MODE is OFF (Usually because user turned it off)",
        17: "PV input is higher than operation range (too high for 150V Classic)",
        18: "PV input is higher than operation range (too high for 200V Classic)",
        19: "PV input is higher than operation range (too high for 250V or 250KS)",
        22: "Average Battery Voltage is too high above set point",
        25: "Battery Voltage too high of Overshoot (small battery or bad cable ?)",
        26: "Mode changed while running OR Vabsorb raised more than 10.0 Volts at once OR Nominal Vbatt changed by modbus command AND MpptMode was ON when changed",
        27: "bridge center == 1023 (R132 might have been stuffed) This turns MPPT Mode to OFF",
        28: "NOT Resting but RELAY is not engaged for some reason",
        29: "ON/OFF stays off because WIND GRAPH is illegal (current step is set for > 100 amps)",
        30: "PkAmpsOverLimit… Software detected too high of PEAK output current",
        31: "AD1CH.IbattMinus > 900 Peak negative battery current > 90.0 amps (Classic 250)",
        32: "Aux 2 input commanded Classic off. for HI or LO (Aux2Function == 15 or 16)",
        33: "OCP in a mode other than Solar or PV-Uset",
        34: "AD1CH.IbattMinus > 900 Peak negative battery current > 90.0 amps (Classic 150, 200)",
        35: "Battery voltage is less than Low Battery Disconnect (LBD) Typically Vbatt is less than 8.5 volts",
        104: "104?=14?: PV input is available but V is rising too slowly. Low Light or bad connection(Solar mode)",
        }
    try:
        decoded["ReasonForRestingText"] = rest_reason_arr[decoded["ReasonForResting"]]
    except:
        log.error("ReasonForRestingText Error ")

    return decoded
