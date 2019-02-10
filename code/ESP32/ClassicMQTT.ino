/*
	Name:       ClassicMQTT.ino
	Created:	1/1/2019 6:54:32 PM
	Author:     SKYE\Me
*/


#include <FS.h>                   //this needs to be first, or it all crashes and burns...

#if defined(ESP8266)
#include <ESP8266WiFi.h>          //https://github.com/esp8266/Arduino
#else
#include <WiFi.h>          //https://github.com/esp8266/Arduino
#endif

//needed for library
#include <DNSServer.h>
#if defined(ESP8266)
#include <ESP8266WebServer.h>
#else
#include <WebServer.h>
#endif
#include <WiFiManager.h>          //https://github.com/tzapu/WiFiManager

#include <ArduinoJson.h>          //https://github.com/bblanchon/ArduinoJson

#include <ArduinoOTA.h>
#include <PubSubClient.h>
#include <esp32ModbusTCP.h>
#include <BlynkSimpleEsp32.h>

#include "Configuration.h"
#include "ChargeControllerInfo.h"

#define BLYNK_PRINT Serial // Enables Serial Monitor
#define MODBUS_POLL_RATE 5000
#define WAKE_PUBLISH_RATE 5000
#define SNOOZE_PUBLISH_RATE 300000
#define WAKE_COUNT 60
#define JSON_BUFFER_SIZE 2018

const int PIN_AP = 0; // press 'boot' button to factory reset
bool _otaInProgress = false;
unsigned long _lastPublishTimeStamp = 0;
unsigned long _lastModbusPollTimeStamp = 0;
unsigned long _publishRate = SNOOZE_PUBLISH_RATE;
int _publishCount = 0;
uint32_t boilerPlatePollRate = 0;
WiFiClient _EspClient;
WiFiManager wifiManager;
bool WiFiConnected = false;
PubSubClient _MqttClient(_EspClient);
String fullTopic_PUB;
bool mqttReadingsAvailable = false;
bool boilerPlateInfoPublished = false;
uint8_t boilerPlateReadBitField = 0;
ChargeControllerInfo _chargeControllerInfo;
esp32ModbusTCP _classic(10, { 192, 168, 86, 37 }, 502);
Configuration _config;
bool shouldSaveConfig = false;
int _currentRegister = 0;

#define numBanks (sizeof(_registers)/sizeof(ModbusRegisterBank))
ModbusRegisterBank _registers[] = {
	{ false, 4100, 44 },
	{ false, 4360, 22 },
	{ false, 4163, 2 },
	{ false, 4209, 4 },
	{ false, 4243, 32 }
//{ false, 16386, 8 }
};

//callback notifying us of the need to save config
void saveConfigCallback() {
	shouldSaveConfig = true;
}

void configModeCallback(WiFiManager *myWiFiManager) {
	Serial.print("Entered config mode: ");
	Serial.println(WiFi.softAPIP());
	//if you used auto generated SSID, print it
	Serial.println(myWiFiManager->getConfigPortalSSID());
}

// note, add 0.01 as a work around for Android JSON deserialization bug with float
void publishReadings() {
	char mqttMessageBuffer[JSON_BUFFER_SIZE];
	if ((boilerPlateReadBitField & 0x0f) == 0x0f && boilerPlateInfoPublished == false) {
		boilerPlateInfoPublished = true;
		StaticJsonBuffer<JSON_BUFFER_SIZE> jsonReadingsBuffer;
		jsonReadingsBuffer.clear();
		JsonObject& root = jsonReadingsBuffer.createObject();
		root["appVersion"] = _chargeControllerInfo.appVersion;
		root["buildDate"] = _chargeControllerInfo.buildDate;
		root["deviceName"] = _chargeControllerInfo.deviceName;
		root["deviceType"] = "Classic";
		root["endingAmps"] = _chargeControllerInfo.endingAmps + 0.01;
		root["hasWhizbang"] = _chargeControllerInfo.hasWhizbang;
		root["lastVOC"] = _chargeControllerInfo.lastVOC + 0.01;
		root["model"] = _chargeControllerInfo.model;
		root["mpptMode"] = _chargeControllerInfo.mpptMode;
		root["netVersion"] = _chargeControllerInfo.netVersion;
		root["nominalBatteryVoltage"] = _chargeControllerInfo.nominalBatteryVoltage;
		root["unitID"] = _chargeControllerInfo.unitID;
		root.printTo(mqttMessageBuffer);
		publish("info", mqttMessageBuffer);
	}
	StaticJsonBuffer<JSON_BUFFER_SIZE> jsonReadingsBuffer;
	jsonReadingsBuffer.clear();
	JsonObject& root = jsonReadingsBuffer.createObject();
	root["BatTemperature"] = _chargeControllerInfo.BatTemperature + 0.01;
	root["NetAmpHours"] = _chargeControllerInfo.NetAmpHours;
	root["ChargeState"] = _chargeControllerInfo.ChargeState;
	root["InfoFlagsBits"] = _chargeControllerInfo.InfoFlagsBits;
	root["ReasonForResting"] = _chargeControllerInfo.ReasonForResting;
	root["NegativeAmpHours"] = _chargeControllerInfo.NegativeAmpHours;
	root["BatVoltage"] = _chargeControllerInfo.BatVoltage + 0.01;
	root["PVVoltage"] = _chargeControllerInfo.PVVoltage + 0.01;
	root["VbattRegSetPTmpComp"] = _chargeControllerInfo.VbattRegSetPTmpComp;
	root["TotalAmpHours"] = _chargeControllerInfo.TotalAmpHours;
	root["WhizbangBatCurrent"] = _chargeControllerInfo.WhizbangBatCurrent + 0.01;
	root["BatCurrent"] = _chargeControllerInfo.BatCurrent + 0.01;
	root["PVCurrent"] = _chargeControllerInfo.PVCurrent + 0.01;
	root["ConnectionState"] = 0;
	root["EnergyToday"] = _chargeControllerInfo.EnergyToday + 0.01;
	root["EqualizeTime"] = _chargeControllerInfo.EqualizeTime;
	root["SOC"] = _chargeControllerInfo.SOC;
	root["Aux1"] = _chargeControllerInfo.Aux1;
	root["Aux2"] = _chargeControllerInfo.Aux2;
	root["Power"] = _chargeControllerInfo.Power + 0.01;
	root["FETTemperature"] = _chargeControllerInfo.FETTemperature + 0.01;
	root["PositiveAmpHours"] = _chargeControllerInfo.PositiveAmpHours;
	root["TotalEnergy"] = _chargeControllerInfo.TotalEnergy + 0.01;
	root["FloatTimeTodaySeconds"] = _chargeControllerInfo.FloatTimeTodaySeconds;
	root["RemainingAmpHours"] = _chargeControllerInfo.RemainingAmpHours;
	root["AbsorbTime"] = _chargeControllerInfo.AbsorbTime;
	root["ShuntTemperature"] = _chargeControllerInfo.ShuntTemperature + 0.01;
	root["PCBTemperature"] = _chargeControllerInfo.PCBTemperature + 0.01;
	root.printTo(mqttMessageBuffer);
	publish("readings", mqttMessageBuffer);
}

void publish(const char* topic, char* value) {
	char mqtt_topic[255];
	snprintf_P(mqtt_topic, sizeof(mqtt_topic), "%s/%s", fullTopic_PUB.c_str(), topic);
	Serial.print("topic: ");
	Serial.println(mqtt_topic);
	Serial.print("value: ");
	Serial.println(value);
	Serial.print("length: ");
	Serial.println(strlen(value));
	if (_MqttClient.beginPublish(mqtt_topic, strlen(value), false) == 1) {
		_MqttClient.print(value);
		_MqttClient.endPublish();
	}
	else {
		Serial.println("beginPublish failed");
	}
}

float GetFloatValue(int index, uint8_t* data, float div = 1.0) {
	index *= 2;
	return (data[index] << 8 | data[index + 1]) / div;
}

uint16_t Getint16Value(int index, uint8_t* data) {
	index *= 2;
	return (data[index] << 8 | data[index + 1]);
}

uint32_t Getint32Value(int index, uint8_t* data) {
	index *= 2;
	return data[index + 2] << 24 | data[index + 3] << 16 | data[index] << 8 | data[index + 1];
}

uint8_t GetMSBValue(int index, uint8_t* data) {
	index *= 2;
	return (data[index] >> 8);
}

boolean GetFlagValue(int index, uint16_t mask, uint8_t* data) {
	index *= 2;
	return (data[index] & mask) != 0;
}

void readModbus() {
	if (_currentRegister < numBanks) {
		if (_registers[_currentRegister].received == false) {
			if (_classic.readHoldingRegister(_registers[_currentRegister].address, _registers[_currentRegister].byteCount) != 0) {
				Serial.printf("Requesting %d for %d bytes\n", _registers[_currentRegister].address, _registers[_currentRegister].byteCount);
			}
			else {
				Serial.printf("Request %d failed\n", _registers[_currentRegister].address);
			}
		}
		_currentRegister++;
	}
}

void SetBankReceived(uint16_t byteCount) {
	int regCount = byteCount / 2;
	for (int i = 0; i < numBanks; i++) {
		if (_registers[i].byteCount == regCount) {
			_registers[i].received = true;
		}
	}
}

//void ClearAllReceived() {
//	boilerPlateReadBitField = 0;
//	for (int i = 0; i < numBanks; i++) {
//		_registers[i].received = false;
//	}
//}

void Wake() {
	_publishRate = WAKE_PUBLISH_RATE;
	_lastPublishTimeStamp = 0;
	_lastModbusPollTimeStamp = 0;
}

void MQTT_callback(char* topic, byte* payload, unsigned int data_len) {
	Serial.print("Message arrived [");
	Serial.print(topic);
	Serial.print("] ");
	for (int i = 0; i < data_len; i++) {
		Serial.print((char)payload[i]);
	}
	Serial.println();

	char* data = (char*)payload;
	if (strncmp(data, "{\"wake\"}", data_len) == 0) {
		boilerPlateInfoPublished = false;
		Wake();
		Serial.println("Wake poll rate");
	}
	if (strncmp(data, "{\"info\"}", data_len) == 0) {
		boilerPlateInfoPublished = false;
		Wake();
		Serial.println("info request received");
	}
}

void modbusCallback(uint16_t packetId, uint8_t slaveAddress, MBFunctionCode functionCode, uint8_t* data, uint16_t byteCount) {
	Serial.print("\n............");
	Serial.printf("packetId[0x%x], slaveAddress[0x%x], functionCode[0x%x], byteCount[%d]", packetId, slaveAddress, functionCode, byteCount);
	Serial.println("............");
	SetBankReceived(byteCount);
	if (byteCount == 88) {
		_chargeControllerInfo.BatVoltage = GetFloatValue(14, data, 10.0);
		_chargeControllerInfo.PVVoltage = GetFloatValue(15, data, 10.0);
		_chargeControllerInfo.BatCurrent = GetFloatValue(16, data, 10.0);
		_chargeControllerInfo.EnergyToday = GetFloatValue(17, data, 10.0);
		_chargeControllerInfo.Power = GetFloatValue(18, data);
		_chargeControllerInfo.ChargeState = GetMSBValue(19, data);
		_chargeControllerInfo.PVCurrent = GetFloatValue(20, data, 10.0);
		_chargeControllerInfo.TotalEnergy = Getint32Value(25, data) / 10.0;
		_chargeControllerInfo.InfoFlagsBits = Getint32Value(29, data);
		_chargeControllerInfo.BatTemperature = GetFloatValue(31, data, 10.0);
		_chargeControllerInfo.FETTemperature = GetFloatValue(32, data, 10.0);
		_chargeControllerInfo.PCBTemperature = GetFloatValue(33, data, 10.0);
		_chargeControllerInfo.FloatTimeTodaySeconds = Getint16Value(37, data);
		_chargeControllerInfo.AbsorbTime = Getint16Value(38, data);
		_chargeControllerInfo.EqualizeTime = Getint16Value(42, data);
		_chargeControllerInfo.Aux1 = GetFlagValue(29, 0x4000, data);
		_chargeControllerInfo.Aux2 = GetFlagValue(29, 0x8000, data);
		
		if ((boilerPlateReadBitField & 0x1) == 0) {
			boilerPlateReadBitField |= 0x1;
			uint16_t reg1 = Getint16Value(0, data);
			char buf[32];
			sprintf(buf, "Classic %d (rev %d)", reg1 & 0x00ff, reg1 >> 8);
			_chargeControllerInfo.model = buf;
			int buildYear = Getint16Value(1, data);
			int buildMonthDay = Getint16Value(2, data);
			sprintf(buf, "%d%02d%02d", buildYear, (buildMonthDay >> 8), (buildMonthDay & 0x00ff));
			_chargeControllerInfo.buildDate = buf;
			_chargeControllerInfo.lastVOC = GetFloatValue(21, data, 10.0);
			_chargeControllerInfo.unitID = Getint32Value(10, data);
		}
	}
	else if (byteCount == 44) { // whizbang readings
		_chargeControllerInfo.PositiveAmpHours = Getint32Value(4, data);
		_chargeControllerInfo.NegativeAmpHours = abs(Getint32Value(6, data));
		_chargeControllerInfo.NetAmpHours = Getint32Value(8, data);
		_chargeControllerInfo.ShuntTemperature = (Getint16Value(11, data) & 0x00ff) - 50.0f;
		_chargeControllerInfo.WhizbangBatCurrent = GetFloatValue(10, data, 10.0);
		_chargeControllerInfo.SOC = Getint16Value(12, data);
		_chargeControllerInfo.RemainingAmpHours = Getint16Value(16, data);
		_chargeControllerInfo.TotalAmpHours = Getint16Value(20, data);
	}
	else if (byteCount == 4) { // boilerplate data
		if ((boilerPlateReadBitField & 0x02) == 0) {
			boilerPlateReadBitField |= 0x02;
			_chargeControllerInfo.mpptMode = Getint16Value(0, data);
			int Aux12FunctionS = (Getint16Value(1, data) & 0x3f00) >> 8;
			_chargeControllerInfo.hasWhizbang = Aux12FunctionS == 18;
		}
	}
	else if (byteCount == 8) { 
		if ((boilerPlateReadBitField & 0x04) == 0) {
			boilerPlateReadBitField |= 0x04;
			char unit[9];
			unit[0] = data[1];
			unit[1] = data[0];
			unit[2] = data[3];
			unit[3] = data[2];
			unit[4] = data[5];
			unit[5] = data[4];
			unit[6] = data[7];
			unit[7] = data[6];
			unit[8] = 0;
			_chargeControllerInfo.deviceName = unit;
		}
	}
	else if (byteCount == 64) {
		if ((boilerPlateReadBitField & 0x08) == 0) {
			boilerPlateReadBitField |= 0x08;
			_chargeControllerInfo.VbattRegSetPTmpComp = GetFloatValue(0, data, 10.0);
			_chargeControllerInfo.nominalBatteryVoltage = Getint16Value(1, data);
			_chargeControllerInfo.endingAmps = GetFloatValue(2, data, 10.0);
			_chargeControllerInfo.ReasonForResting = Getint16Value(31, data);
		}
	}
	else if (byteCount == 16) {
		if ((boilerPlateReadBitField & 0x10) == 0) {
			boilerPlateReadBitField |= 0x10;
			short reg16387 = Getint16Value(0, data);
			short reg16388 = Getint16Value(1, data);
			short reg16389 = Getint16Value(2, data);
			short reg16390 = Getint16Value(3, data);
			char unit[16];
			snprintf_P(unit, sizeof(unit), "%d", (reg16388 << 16) + reg16387);
			_chargeControllerInfo.appVersion = unit;
			snprintf_P(unit, sizeof(unit), "%d", (reg16390 << 16) + reg16389);
			_chargeControllerInfo.netVersion = unit;
		}
	}
}

void setup() {
	Serial.begin(115200);
	while (!Serial) {
		; // wait for serial port to connect. Needed for native USB port only
	}
	Serial.println("Booting");
	pinMode(PIN_AP, INPUT_PULLUP);
	_config.Init();
	_config.Load();
	_config.Print();

	wifiManager.setMinimumSignalQuality();
	wifiManager.setTimeout(120);
	if (_config.IsDefault()) {
		wifiManager.resetSettings();
		SYSCFG* c = _config.Settings();
		WiFiManagerParameter mqtt_server_parameter("server", "mqtt server", c->mqtt_host, 33);
		WiFiManagerParameter mqtt_port_parameter("port", "mqtt port", c->mqtt_port, 6, "type=\"number\" min=\"1024\" max=\"65535\"");
		WiFiManagerParameter mqtt_user_parameter("mqtt_user", "mqtt user", c->mqtt_user, 33);
		WiFiManagerParameter mqtt_password_parameter("mqtt_password", "mqtt password", c->mqtt_pwd, 33, "type=\"password\"");
		WiFiManagerParameter mqtt_root_topic_parameter("mqtt_root_topic", "mqtt root topic", c->mqtt_roottopic, 100);
		WiFiManagerParameter classic_ip_parameter("classic_ip", "Classic IP address", c->classic_ip, 33);
		WiFiManagerParameter classic_port_parameter("classic_port", "Classic port", c->classic_port, 6, "type=\"number\" max=\"65535\"");
		WiFiManagerParameter blynk_token_parameter("blynk", "blynk token", c->blynk_token, 33);
		wifiManager.setAPCallback(configModeCallback);
		wifiManager.setSaveConfigCallback(saveConfigCallback);
		wifiManager.addParameter(&mqtt_server_parameter);
		wifiManager.addParameter(&mqtt_port_parameter);
		wifiManager.addParameter(&mqtt_user_parameter);
		wifiManager.addParameter(&mqtt_password_parameter);
		wifiManager.addParameter(&mqtt_root_topic_parameter);
		wifiManager.addParameter(&classic_ip_parameter);
		wifiManager.addParameter(&classic_port_parameter);
		wifiManager.addParameter(&blynk_token_parameter);
		if (!wifiManager.startConfigPortal("Classic MQTT")) {
			Serial.println("failed to connect and hit timeout");
			delay(1000);
			ESP.restart();
			delay(5000);
		}
		delay(1000);
		Serial.printf("shouldSaveConfig[%u]: ", shouldSaveConfig);
		if (shouldSaveConfig) {
			shouldSaveConfig = false;
			strcpy(c->mqtt_host, mqtt_server_parameter.getValue());
			strcpy(c->mqtt_port, mqtt_port_parameter.getValue());
			strcpy(c->mqtt_user, mqtt_user_parameter.getValue());
			strcpy(c->mqtt_pwd, mqtt_password_parameter.getValue());
			strcpy(c->mqtt_roottopic, mqtt_root_topic_parameter.getValue());
			strcpy(c->classic_ip, classic_ip_parameter.getValue());
			strcpy(c->classic_port, classic_port_parameter.getValue());
			strcpy(c->blynk_token, blynk_token_parameter.getValue());
			_config.Save();
			Serial.println("Saved new configuration");
			_config.Print();
		}
		delay(1000);
		ESP.restart();
		delay(5000);
	}
	else {
		if (!wifiManager.autoConnect("Classic MQTT Auto")) {
			Serial.println("failed to connect and hit timeout");
			delay(3000);
			//reset and try again, or maybe put it to deep sleep
			ESP.restart();
			delay(5000);
		}
	}

	
	/* OTA SETUP */
	// Port defaults to 8266
	// ArduinoOTA.setPort(8266);

	// Hostname defaults to esp8266-[ChipID]
	// ArduinoOTA.setHostname("myesp8266");

	// No authentication by default
	//ArduinoOTA.setPassword((const char *)"volvo4");

	ArduinoOTA.onStart([]() {
		_otaInProgress = true;
		Serial.println("Start");
	});
	ArduinoOTA.onEnd([]() {
		_otaInProgress = false;
		Serial.println("\nEnd");
	});
	ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
		//Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
	});
	ArduinoOTA.onError([](ota_error_t error) {
		Serial.printf("Error[%u]: ", error);
		if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
		else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
		else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
		else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
		else if (error == OTA_END_ERROR) Serial.println("End Failed");
	});
	ArduinoOTA.begin();
	Serial.print("IP address: ");
	Serial.println(WiFi.localIP());
	/* END OF OTA SETUP */

	SYSCFG* c = _config.Settings();
	_MqttClient.setServer(c->mqtt_host, atoi(c->mqtt_port));
	char buf[64];
	sprintf(buf, "/%s/classic/stat", c->mqtt_roottopic);
	fullTopic_PUB = buf;
	Serial.println(fullTopic_PUB);
	_MqttClient.setCallback(MQTT_callback);
	_classic.onData(modbusCallback);
	_classic.begin();
	_lastPublishTimeStamp = millis() + MODBUS_POLL_RATE;
	boilerPlatePollRate = millis();
	Blynk.config(c->blynk_token);
	Blynk.connect();
	Serial.println("Done setup");
}

void loop() {

	ArduinoOTA.handle();
	if (_otaInProgress == false) {
		if (digitalRead(PIN_AP) == LOW) { // reset to AP if the GPIO0 button is pressed
			Serial.println("****************resetSettings*************"); // factory reset
			_config.Default();
			delay(1000);
			ESP.restart();
			delay(1000);
		}
		if (!_MqttClient.connected()) {
			if (_lastPublishTimeStamp < millis()) {
				_lastPublishTimeStamp = millis() + MODBUS_POLL_RATE; // attempt reconnect every MODBUS_POLL_RATE seconds
				Serial.print("Attempting MQTT connection...");
				SYSCFG* c = _config.Settings();
				if (_MqttClient.connect(c->mqtt_client, c->mqtt_user, c->mqtt_pwd)) {
					Serial.println("connected");
					// Once connected, publish an announcement...
					publish("state", "ONLINE");
					// ... and resubscribe
					char buf[64];
					sprintf(buf, "/%s/classic/cmnd/#", c->mqtt_roottopic);
					_MqttClient.subscribe(buf);
				}
				else {
					Serial.print("failed, rc=");
					Serial.print(_MqttClient.state());
					Serial.println(" try again in a few seconds");
				}
			}
		}
		else {
			if (_lastModbusPollTimeStamp < millis()) {
				_lastModbusPollTimeStamp = millis() + MODBUS_POLL_RATE;
				readModbus();
				if (_currentRegister >= numBanks) {
					_currentRegister = 0;
					_registers[0].received = false; // repeat readings
					_registers[1].received = false;
				}
			}
			_MqttClient.loop();
			if (_lastPublishTimeStamp < millis()) {
				_lastPublishTimeStamp = millis() + _publishRate;
				_publishCount++;
				publishReadings();
				//if (Blynk.connected()) {
				//	Blynk.virtualWrite(V6, _chargeControllerInfo.Power);
				//	Blynk.virtualWrite(V5, _chargeControllerInfo.BatVoltage);
				//}
			}
		}
		if (_publishCount >= WAKE_COUNT) {
			_publishCount = 0;
			_publishRate = SNOOZE_PUBLISH_RATE;
			Serial.println("**** Snooze poll rate");

		}
		Blynk.run();
	}
}


BLYNK_READ(V0)
{
	Blynk.virtualWrite(V0, _chargeControllerInfo.BatVoltage);
}

BLYNK_READ(V1)
{
	Blynk.virtualWrite(V1, _chargeControllerInfo.BatCurrent);
}

BLYNK_READ(V2)
{
	Blynk.virtualWrite(V2, _chargeControllerInfo.SOC);
}
BLYNK_READ(V3)
{
	Blynk.virtualWrite(V3, _chargeControllerInfo.Power);
}
BLYNK_READ(V4)
{
	Blynk.virtualWrite(V4, _chargeControllerInfo.PVVoltage);
}
BLYNK_READ(V5)
{
	Blynk.virtualWrite(V5, _chargeControllerInfo.PVCurrent);
}
