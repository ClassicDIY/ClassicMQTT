#!/usr/bin/env python
 
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.compat import iteritems
from collections import OrderedDict
import logging
import sys


log = logging.getLogger('classic_mqtt')

# --------------------------------------------------------------------------- # 
# Read from the address and return a decoder
# --------------------------------------------------------------------------- # 
def getRegisters(theClient, addr, count):
    try:
        result = theClient.read_holding_registers(addr, count,  unit=10)
        if result.function_code >= 0x80:
            log.error("error getting {} for {} bytes".format(addr, count))
            return {}
    except:
        log.error("Error getting {} for {} bytes".format(addr, count))
        return {}


    return result.registers


def getDataDecoder(registers):
    return BinaryPayloadDecoder.fromRegisters(
        registers,
        byteorder=Endian.Big,
        wordorder=Endian.Little)


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
            ('unitID', decoder.decode_32bit_int()),                    #4111
            ('StatusRoll', decoder.decode_16bit_uint()),               #4113
            ('RsetTmms', decoder.decode_16bit_uint()),                 #4114
            ('BatVoltage', decoder.decode_16bit_int()/10.0),           #4115
            ('PVVoltage', decoder.decode_16bit_uint()/10.0),           #4116
            ('BatCurrent', decoder.decode_16bit_uint()/10.0),          #4117
            ('EnergyToday', decoder.decode_16bit_uint()/10.0),         #4118
            ('Power', decoder.decode_16bit_uint()/1.0),                #4119
            ('ChargeState', decoder.decode_8bit_uint()),               #4120 MSB
            ('State', decoder.decode_8bit_uint()),                     #4120 LSB
            ('PVCurrent', decoder.decode_16bit_uint()/10.0),           #4121
            ('lastVOC', decoder.decode_16bit_uint()/10.0),             #4122
            ('HighestVinputLog', decoder.decode_16bit_uint()),         #4123
            ('MatchPointShadow', decoder.decode_16bit_uint()),         #4124
            ('AmpHours', decoder.decode_16bit_uint()),                 #4125
            ('TotalEnergy', decoder.decode_32bit_uint()/10.0),         #4126, 4127
            ('LifetimeAmpHours', decoder.decode_32bit_uint()),         #4128, 4129
            ('InfoFlagsBits', decoder.decode_32bit_int()),             #4130, 31
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
            ('Name0', decoder.decode_8bit_uint()),                      #4210
            ('Name1', decoder.decode_8bit_uint()),                      #4211
            ('Name2', decoder.decode_8bit_uint()),                      #4212
            ('Name3', decoder.decode_8bit_uint()),                      #4213
            ('Name4', decoder.decode_8bit_uint()),                      #4214
            ('Name5', decoder.decode_8bit_uint()),                      #4215
            ('Name6', decoder.decode_8bit_uint()),                      #4216
            ('Name7', decoder.decode_8bit_uint()),                      #4217
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
# Run the main payload decoder
# --------------------------------------------------------------------------- # 
def getModbusData():

    try:
        modclient = ModbusClient(classicHost, port=classicPort)
        #Test for succesful connect, if not, log error and mark modbusConnected = False
        modclient.connect()

        result = modclient.read_holding_registers(4163, 2,  unit=10)
        if result.isError():
            # close the client
            log.error("MODBUS isError H:{} P:{} count:{}".format(classicHost, classicPort, modbusErrorCount))
            modclient.close()
            return {}

        theData = {}
        #Read in all the registers at one time
        theData[4100] = getRegisters(theClient=modclient,addr=4100,count=44)
        theData[4360] = getRegisters(theClient=modclient,addr=4360,count=22)
        theData[4163] = getRegisters(theClient=modclient,addr=4163,count=2)
        theData[4209] = getRegisters(theClient=modclient,addr=4209,count=4)
        theData[4243] = getRegisters(theClient=modclient,addr=4243,count=32)
        theData[16386]= getRegisters(theClient=modclient,addr=16386,count=4)
        modclient.close()

    except: # Catch all modbus excpetions
        e = sys.exc_info()[0]
        log.error("MODBUS Error H:{} P:{} e:{}".format(classicHost, classicPort, e))
        try:
            modclient.close()
        except:
            log.error("MODBUS Error on close H:{} P:{} e:{}".format(classicHost, classicPort, e))
        return {}

    log.debug("Got data from Classic at {}:{}".format(mqttHost,mqttPort))

    #Iterate over them and get the decoded data all into one dict
    decoded = {}
    for index in theData:
        decoded = {**dict(decoded), **dict(doDecode(index, getDataDecoder(theData[index])))}

    return decoded

