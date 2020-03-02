
<h1>Classic Monitor MQTT publisher Python implementation</h1>

<p>
Classic Monitor MQTT will read data from your classic over Modbus and publish it to a MQTT broker. It is a Read Only Program, it does not write to the Classic.

The software is provided "AS IS", WITHOUT WARRANTY OF ANY KIND, express or implied.
Classic Monitor is NOT a product of Midnite solar, nor do they support this application!
</p>

Release notes:
-----------------
version 1.0.0
<p>
This tool is meant to run on a computer system that can reach a Midnite Classic Solar MPPT Controller. It will periodically connect to the
Classic using MODBUS and then format that data into a JSON format and post it onto an MQTT server. An example installation would be a Raspberry Pi
running on the local network with the Classic and has an MQTT service installed on it (like Mosquitto). The data would be collected by the tool
and posted onto the MQTT service.
<p>
It requires Python 3 and these packages be installed on the system to operate correctly:
+Pymodbus
+paho-mqtt
<p>
The following are the parameters that can be passed to the script
<p>
`classic_mqtt.py --classic <ClassicHost> --classic_port <502> --mqtt <127.0.0.1> --mqtt_port <1883> --mqtt_root <ClassicMQTT> --user <username> --pass <password>`

-----------------
