MODBUS_POLL_RATE = 5                #Get data from the Classic every 5 seconds
MQTT_PUBLISH_RATE = 5               #Check to see if anything needs publishing every 5 seconds.
MQTT_SNOOZE_COUNT = 60              #When no one is listening, publish every 5 minutes
WAKE_COUNT = 60                     #The number of times to publish after getting a "wake"
MQTT_ROOT_DEFAULT = "ClassicMQTT"

mqttRoot = MQTT_ROOT_DEFAULT
classicModbusData = dict()
snoozeCount = 0
snoozing = True
wakeCount = 0
infoPublished = True
doStop = False