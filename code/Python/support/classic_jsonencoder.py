#!/usr/bin/env python

# --------------------------------------------------------------------------- # 
# Handle creating the Json packaging of the Modbus data.
# 
# --------------------------------------------------------------------------- # 


import json
import logging
import datetime

log = logging.getLogger('classic_mqtt')


# --------------------------------------------------------------------------- # 
# Handle creating the Json for Readings
# --------------------------------------------------------------------------- # 
def encodeClassicData_readings(decoded):
    log.debug("Enter encodeClassicData_readings")

    classicData = {}

    # "BatTemperature":-1.99,
    classicData["BatTemperature"] = decoded["BatTemperature"]
    # "NetAmpHours":0,
    classicData["NetAmpHours"] = decoded["WbJrAmpHourNET"]
    # "ChargeState":0,
    classicData["ChargeState"] = decoded["ChargeStage"] #it is mis-labeled in the ESP32 code
    # "InfoFlagsBits":-1308610300,
    classicData["InfoFlagsBits"] = decoded["InfoFlagsBits"]
    # "ReasonForResting":104,
    classicData["ReasonForResting"] = decoded["ReasonForResting"]
    # "NegativeAmpHours":-9170,
    classicData["NegativeAmpHours"] = decoded["WbJrAmpHourNEGative"]
    # "BatVoltage":25.21,
    classicData["BatVoltage"] = decoded["BatVoltage"]
    # "PVVoltage":10.21,
    classicData["PVVoltage"] = decoded["PVVoltage"]
    # "VbattRegSetPTmpComp":30.6,
    classicData["VbattRegSetPTmpComp"] = decoded["VbattRegSetPTmpComp"]
    # "TotalAmpHours":676,
    classicData["TotalAmpHours"] = decoded["TotalAmpHours"]
    # "WhizbangBatCurrent":-0.59,
    classicData["WhizbangBatCurrent"] = decoded["WhizbangBatCurrent"]
    # "BatCurrent":0.01,
    classicData["BatCurrent"] = decoded["BatCurrent"]
    # "PVCurrent":0.01,
    classicData["PVCurrent"] = decoded["PVCurrent"]
    # "ConnectionState":0,
    classicData["ConnectionState"] = 0
    # "EnergyToday":0.01,
    classicData["EnergyToday"] = decoded["EnergyToday"]
    # "EqualizeTime":10800,
    classicData["EqualizeTime"] = decoded["EqualizeTime"]
    # "SOC":99,
    classicData["SOC"] = decoded["SOC"]
    # "Aux1":false,
    classicData["Aux1"] = ((decoded["InfoFlagsBits"] & 0x4000) == 1)
    # "Aux2":false,
    classicData["Aux2"] = ((decoded["InfoFlagsBits"] & 0x8000) == 1)
    # "Power":0.01,
    classicData["Power"] = decoded["Power"]
    # "FETTemperature":4.31,
    classicData["FETTemperature"] = decoded["FETTemperature"]
    # "PositiveAmpHours":16797,
    classicData["PositiveAmpHours"] = decoded["WbJrAmpHourPOSitive"]
    # "TotalEnergy":603.41,
    classicData["TotalEnergy"] = decoded["TotalEnergy"]
    # "FloatTimeTodaySeconds":0,
    classicData["FloatTimeTodaySeconds"] = decoded["FloatTimeTodaySeconds"]
    # "RemainingAmpHours":673,
    classicData["RemainingAmpHours"] = decoded["RemainingAmpHours"]
    # "AbsorbTime":18000,
    classicData["AbsorbTime"] = decoded["AbsorbTime"]
    # "ShuntTemperature":0.01,
    classicData["ShuntTemperature"] = decoded["ShuntTemperature"]
    # "PCBTemperature":12.71
    classicData["PCBTemperature"] = decoded["PCBTemperature"]

    return json.dumps(classicData, sort_keys=False, separators=(',', ':'))

# --------------------------------------------------------------------------- # 
# Handle creating the Json for Info
# --------------------------------------------------------------------------- # 
def encodeClassicData_info(decoded):

    log.debug("Enter encodeClassicData_info")
    classicData = {}
    # "appVersion":"",
    classicData["appVersion"] = decoded["app_rev"]
    #Assemble the string
    uint_array = [decoded["Name1"],decoded["Name0"],decoded["Name3"],decoded["Name2"],decoded["Name5"],decoded["Name4"],decoded["Name7"],decoded["Name6"]]
    # "deviceName":"CLASSIC",
    classicData["deviceName"] = "".join(chr(x) for x in uint_array)
    # "buildDate":"Tuesday, February 6, 2018",
    bdate = datetime.date(decoded["Year"],decoded["Month"],decoded["Day"])
    classicData["buildDate"] = bdate.strftime("%A, %B %d, %Y").replace(' 0', ' ') # get rid of the stupid leading 0 in date.
    # "deviceType":"Classic",
    classicData["deviceType"] = "Classic"
    # "endingAmps":13.01,
    classicData["endingAmps"] = decoded["endingAmps"]
    # "hasWhizbang":true,
    classicData["hasWhizbang"] = (decoded["Aux1and2Function"] & 0x3f00)>>8 == 18
    # "lastVOC":10.21,
    classicData["lastVOC"] = decoded["lastVOC"]
    # "model":"Classic 150 (rev 4)",
    #print("Classic {} (rev {})".format(decoded["Type"],decoded["PCB"]))
    classicData["model"] = "Classic {}V (rev {})".format(decoded["Type"],decoded["PCB"])
    # "mpptMode":11,
    classicData["mpptMode"] = decoded["MPPTMode"]
    # "netVersion":"",
    classicData["netVersion"] = decoded["net_rev"]
    # "nominalBatteryVoltage":24,
    classicData["nominalBatteryVoltage"] = decoded["nominalBatteryVoltage"]
    # "unitID":-791134691
    classicData["unitID"] = decoded["unitID"]

    mac = "{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}".format(decoded["mac_5"],decoded["mac_4"],decoded["mac_3"],decoded["mac_2"],decoded["mac_1"],decoded["mac_0"])
    classicData["macAddress"] = mac.upper()

    return json.dumps(classicData, sort_keys=False, separators=(',', ':'))
