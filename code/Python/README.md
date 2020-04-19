
# Classic Monitor MQTT Publisher Python Implementation

The code in this repository will read data from your Midnite Classic over the TCP based MODBUS interface and publish it to an MQTT broker. It is a read-only program with respect to the Solar Controller, it does not write any data to Classic. It is intended to be used with the Classic Monitor tool developed by Graham, but can also be used to make the data from your Midnite Classic available for other purposes by simply connecting the the MQTT broker and subscribing to the proper subjects.  

The software is provided "AS IS", WITHOUT WARRANTY OF ANY KIND, express or implied.
Classic Monitor is NOT a product of Midnite solar, nor do they support this application!

version 1.0.1  
As the name implies, this tool is implemeted in Python and is meant to run on a computer system that can reach your Midnite Classic Solar MPPT Controller and an MQTT broker over a network. Once launched, the program will periodically connect to the Classic using TCP based MODBUS then upload that data to an MQTT broker where it is availabe for subscription from other programs or apps. An example installation would be a Raspberry Pi running on the local network with the Classic and pushing the data to either a local MQTT broker or one the internet. 

## **Get It**

1. Copy this repository (if you understand git, you can get it that way too)  
    `wget https://github.com/graham22/ClassicMQTT/archive/master.zip`
2. Extract the zip file:  
    `unzip master.zip`
3. Change directory  
     `cd ./ClassicMQTT-master/code/Python`

When it comes time to run the program, there are parameters that can be set or passed they are:  
**Parameters:**  
```  
--classic <ClassicHost>         : The IP address of your Midnite Classic Solar Controller, no default.  
--classic_port <502>            : The prot for the Classic MODBUS, defaults to 502 if unspecified. 
--classic_name <Classic>        : The name used in the Android app when adding a controller to the nav bar. 
--mqtt <127.0.0.1>              : The IP or URL of the MQTT Broker, defaults to 127.0.0.1 if unspecified.  
--mqtt_port <1883>              : The port to you to connect to the MQTT Broker, defaults to 1883 if unspecified.  
--mqtt_root <ClassicMQTT>       : The root for your MQTT topics, defaults to ClassicMQTT if unspecified.  
--mqtt_user <username>          : The username to access the MQTT Broker.  
--mqtt_pass <password>          : The passowrd to access the MQTT Broker.
--wake_publish_rate <seconds>   : The amount of time between updates when in wake mode (5 seconds).
--snooze_publish_rate <seconds> : The amount of time between updates when in snooze mode (5 minutes).
--wake_duration <seconds>       : The amount of time to stay in wake mode after reciving an "info" or "wake" message (15 minutes).
```  

## **Run It**

There are several ways to run this program:

1. **Standalone** - must have an MQTT server available and python 3 installed
2. **docker** - must have an MQTT server available and docker installed
3. **docker-compose** - must have docker and docker-compose installed, provides it's own MQTT broker 

### **1. Standalone**

Make sure that you have access to an MQTT broker; either install one on your server or use one of the internet based ones like [Dioty](http://www.dioty.co/). Once you have that setup, make sure that you have a username and password defined, you will need it to both publish data and to get the data once it is published.  

1. Install Python 3.7 or newer and pip. Consult the documentation for your particular computer.
2. Install these libraries: **pymodbus**, **paho-mqtt**, **timeloop** using pip:  
    ```
    pip install pymodbus paho-mqtt timeloop
    ```   
3. Install or setup access to an MQTT server like [Dioty](http://www.dioty.co/).  Make sure that you have a username and password defined
4. Run the program from the command line where the classic_mqtt.py is located with t eproper parameters:  
    ```
    python3 classic_mqtt.py --classic <ClassicHost> --classic_port <502> --classic_name <Classic> --mqtt <127.0.0.1> --mqtt_root <ClassicMQTT> --mqtt_user <username> --mqtt_pass <password> --snooze_secs <300>
    ```
    **Example**:  
    If your Classic is at IP address 192.168.0.225 and named "Classic" and your mqtt server is Dioty, the settings would look like this:  
    ```
    python3 classic_mqtt.py --classic 192.168.0.225 --classic_name Classic --mqtt mqtt.dioty.co --mqtt_root /joe.user@gmail.com/ClassicMQTT --mqtt_user joe.user@gmail.com --mqtt_pass <Joe's Dioty password>
    ```  

### **2. Using docker**

Using the "Dockerfile" in this directory will allow an image to be built that can run the program. The Dockerfile uses a base image that already includes python and instructions to install the 3 needed libraries so you can skip installing python and pip, but you must install docker.  

1. Install docker on your host - look this up on the web and follow the instructions for your computer.
2. Install or setup access to an MQTT server like [Dioty](http://www.dioty.co/).  Make sure that you have a username and password defined
3. Issue the following command to build the docker image in the docker virtual environment (only need to do this once):  
    ```
    docker build -t classic_mqtt .
    ```
4. Run the docker image and pass the parameters (substituing the correct values for parameter values):  
    ```
    docker run classic_mqtt --classic <ClassicHost> --classic_port <502> --classic_name <Classic> --mqtt <127.0.0.1> --mqtt_port <1883> --mqtt_root <ClassicMQTT> --mqtt_user <username> --mqtt_pass <password>
    ```
5. For example, if your Classic is at IP address 192.168.0.225 and named "classic" and your mqtt server is Dioty, the docker run command would look similar to this:  
    ```
    docker run classic_mqtt --classic 192.168.0.225 --classic_name classic --mqtt mqtt.dioty.co --mqtt_root /joe.user@gmail.com --mqtt_user joe.user@gmail.com --mqtt_pass <Joe's Dioty password>
    ```  


### **3. Using docker-compose**

Use this method if you want to automatically install an MQTT broker (mosquitto) locally and run the program at the same time. This method takes advantage of docker-compose which will build a system that includes both an MQTT service and a service running the classic_mqtt.py script automatically. The definition for thse services are in classic_mqtt_compose.yml. If you are pushing your data to the internet, this may not be the preferred method for you.
Note: if you need to change anything in the yml file or the ".env" file, you need to tell docker-compose to rebuild the images with the command listed in step 4 below.  

1. Install docker and docker-compose on your host - look this up on the web and follow the instructions for your computer.
2. Create the .env file and specify the 5 items listed below in this format. They correspond to the parameters for the classic_mqtt.py program. Notice that since we are bringing up our own MQTT Broker, we can skip specifying the MQTT host. The last 3 parameters will work with the included MQTT broker, so there is no need to change those. To create this file on the Raspberry Pi, I like nano.
    ```
    CLASSIC=<IP address or URL>  
    CLASSIC_PORT=<Port usually 502>
    CLASSIC_NAME=Classic
    MQTT_ROOT=ClassicMQTT 
    MQTT_USER=ClassicPublisher 
    MQTT_PASS=ClassicPub123
    ```
3. Tell docker-compose to download, build and start up the both mosquitto and the script with the following command.
    ```
    docker-compose -f classic_mqtt_compose.yml up
    ```
4. Only use this if you change the .env file or anything classic_mqtt_compose.yml or Dockerfile once you have already run the command in step 3 above. This tells docker-compose to rebuild and save the images use the command in step 3 to run it:
    ```
    docker-compose -f classic_mqtt_compose.yml build
    ```
