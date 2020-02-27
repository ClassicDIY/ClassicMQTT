
<h1>Classic Monitor MQTT publisher Python implementation</h1>


<p>
Classic Monitor MQTT will read data from your classic over Modbus and publish it to a MQTT broker. It is a Read Only Program, it does not write to the Classic.

The software is provided "AS IS", WITHOUT WARRANTY OF ANY KIND, express or implied.
Classic Monitor is NOT a product of Midnite solar, nor do they support this application!
</p>

Release notes:
-----------------
version 1.0.0

<ul>
<li>Initial Release</li>
</ul>

Use: <p>
`classic_mqtt.py --classic <ClassicHost> --classic_port <502> --mqtt <127.0.0.1> --mqtt_port <1883> --mqtt_root <ClassicMQTT> --user <username> --pass <password>`

-----------------
