#pragma once
#include <stdint.h>
#include <WString.h>

struct ChargeControllerInfo
{

	int32_t unitID = 0;
	String deviceName = "";
	bool hasWhizbang = false;

	String model;
	float lastVOC = 0;
	String appVersion = "";
	String netVersion = "";
	String buildDate = "";
	uint16_t nominalBatteryVoltage = 0;
	uint16_t mpptMode = 0;
	float endingAmps = 0;
	float BatVoltage = 0;
	float PVVoltage = 0;
	float BatCurrent = 0;
	float EnergyToday = 0;
	float Power = 0;
	uint16_t ChargeState = 0;
	float PVCurrent = 0;
	float TotalEnergy = 0;
	int32_t InfoFlagsBits = 0;
	float BatTemperature = 0;
	float FETTemperature = 0;
	float PCBTemperature = 0;
	uint16_t FloatTimeTodaySeconds = 0;
	uint16_t AbsorbTime = 0;
	uint16_t EqualizeTime = 0;
	bool Aux1 = false;
	bool Aux2 = false;
	uint32_t PositiveAmpHours = 0;
	int32_t NegativeAmpHours = 0;
	uint32_t NetAmpHours = 0;
	float ShuntTemperature = 0;
	float WhizbangBatCurrent = 0;
	uint16_t SOC = 0;
	uint16_t RemainingAmpHours = 0;
	uint16_t TotalAmpHours = 0;
	float VbattRegSetPTmpComp = 0;
	uint16_t ReasonForResting = 0;
};

typedef struct 
{
	bool received;
	int address;
	int byteCount;
} ModbusRegisterBank;

