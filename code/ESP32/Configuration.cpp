#include <WiFi.h>
#include "Configuration.h"


Configuration::Configuration()
{
}

void Configuration::Init()
{
	if (!EEPROM.begin(EEPROM_SIZE)) {
		Serial.println("Failed to initialise EEPROM");
		_settings.top = EEPROM_IS_EMPTY;
	}
}

void Configuration::Load()
{
	if (byte(EEPROM.read(0)) == EEPROM_IS_VALID) {
		uint8_t version_major = EEPROM.readByte(1);
		if (version_major != VERSION_MAJOR) {
			Serial.println("Wrong version in EEPROM");
			Serial.printf("version: 0x%X\n", version_major);
			for (int i = 0; i < EEPROM_SIZE; i++)
			{
				Serial.printf ("0x%X ", byte(EEPROM.read(i)));
			}
			Default();
		}
		else {
			byte* ptr = &_settings.top;
			for (int i = 0; i < EEPROM_SIZE; i++)
			{
				ptr[i] = byte(EEPROM.read(i));
			}
		}
	}
	else {
		Serial.println("Nothing in EEPROM");
		Default();
	}
}

void Configuration::Save()
{
	_settings.top = EEPROM_IS_VALID;
	byte* ptr = &_settings.top;
	for (int i = 0; i < EEPROM_SIZE; i++)
	{
		EEPROM.write(i, ptr[i]);
	}
	EEPROM.commit();
}


void Configuration::Default()
{
	char tmp[20];
	uint8_t mac[6];
	WiFi.macAddress(mac);
	sprintf(tmp, "esp32-%02x%02x%02x%02x%02x%02x", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
	_settings.top = EEPROM_IS_DEFAULT;
	_settings.version_major = VERSION_MAJOR;
	_settings.version_minor = VERSION_MINOR;
	strcpy(_settings.mqtt_host, MQTT_HOST);
	strcpy(_settings.mqtt_port, MQTT_PORT);
	strcpy(_settings.mqtt_client, tmp);
	strcpy(_settings.mqtt_user, MQTT_USER);
	strcpy(_settings.mqtt_pwd, MQTT_PASSWORD);
	strcpy(_settings.mqtt_roottopic, MQTT_ROOTTOPIC);
	strcpy(_settings.blynk_token, "");
	byte* ptr = &_settings.top;
	for (int i = 0; i < EEPROM_SIZE; i++)
	{
		EEPROM.write(i, ptr[i]);
	}
	EEPROM.commit();
	Serial.println("Loaded default settings");
}

boolean Configuration::IsDefault() {
	return _settings.top == EEPROM_IS_DEFAULT;
}

void Configuration::Print() {
	Serial.printf("top: 0x%X\n version_major: 0x%X\n version_minor: 0x%X\n mqtt_host: %s\n  mqtt_port: %s\n mqtt_client: %s\n mqtt_user: %s\n mqtt_pwd: %s\n mqtt_fulltopic: %s\n classic_ip: %s\n classic_port: %s blynk_token: %s\n",
		_settings.top, _settings.version_major, _settings.version_minor, _settings.mqtt_host, _settings.mqtt_port, _settings.mqtt_client, 
		_settings.mqtt_user, _settings.mqtt_pwd, _settings.mqtt_roottopic, _settings.classic_ip, _settings.classic_port, _settings.blynk_token);
}
