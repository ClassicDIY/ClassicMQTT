
<h1>Classic Monitor MQTT publisher Python implementation</h1>

<p>
Classic Monitor MQTT will read data from your classic over Modbus and publish it to an MQTT broker. It is a Read Only Program, it does not write to the Classic.

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

+ Pymodbus
+ paho-mqtt
<p>
It has been packaged into a format that allows it to be built and run using Docker, particularly docker-compose. This will take care of installing the correct version of Python and the needed libraries, so no need to intall any of that on your Pi.

To get this to run on a Raspberry Pi follow these steps:
1. Install docker and docker-compose on your Rasberry Pi - look this up on the web and follow the instructions.
2. Copy the repostory (if you understand git, you can get it that way too)\
    `wget https://github.com/graham22/ClassicMQTT/archive/master.zip`
3. Extract the zip file:\
    `unzip master.zip `
4. Change directory\
    `cd ./ClassicMQTT/code/Python`
5. Create the .env file to look like this:\
    `CLASSIC_HOST=<IP address or URL>`\
    `CLASSIC_PORT=<Port usually 502>`\
    `CLASSIC_ROOT=<The MQTT Root, usually ClassicMQTT>`\
    `USER_ID=ClassicPublisher`\
    `USER_PASS=ClassicPub123`
6. User docker-compose to start up the both the mosquitto and the script.\
    `docker-compose -f classic_mqtt_compose.yml up`

\
If you are just going to run the python script you will need to install pymodbus and paho-mqtt then you can use it as in the following:\
`classic_mqtt.py --classic <ClassicHost> --classic_port <502> --mqtt <127.0.0.1> --mqtt_port <1883> --mqtt_root <ClassicMQTT> --user <username> --pass <password>`
