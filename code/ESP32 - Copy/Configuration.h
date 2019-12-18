#pragma once
#include <stdint.h>
#include "EEPROM.h"

#define VERSION_MAJOR  0x01
#define VERSION_MINOR  0x00 // change does not reset EEPROM
#define EEPROM_IS_EMPTY  0x00
#define EEPROM_IS_DEFAULT  0xFF
#define EEPROM_IS_VALID  0x55
#define MQTT_HOST "mqtt.dioty.co"
#define MQTT_PORT "1883"

struct SYSCFG {
	byte	    top;
	uint8_t		version_major;
	uint8_t		version_minor;
	char        classic_ip[34];
	char        classic_port[7];
	char        mqtt_host[34];
	char		mqtt_port[7];
	char        mqtt_client[34];
	char        mqtt_user[34];
	char        mqtt_pwd[34];
	char        mqtt_roottopic[101];
	char		blynk_token[34];
};

#define EEPROM_SIZE sizeof(SYSCFG)

class Configuration
{
public:
	Configuration();
	void Init();
	void Load();
	void Save();
	void Default();
	boolean IsDefault();
	void Print();
	SYSCFG* Settings() {
		return &_settings;
	};

private:
	SYSCFG _settings;
};

