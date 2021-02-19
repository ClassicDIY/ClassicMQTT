
# Classic MQTT Client Example

The code in this folder is and example of how to create and mqtt cleint that receives data that was posted to the MQTT from ClassicMQTT. It is very simple, just creating an MQTT client and making a subscription. When the client recceives data it will rewite it with the data received.  

The software is provided "AS IS", WITHOUT WARRANTY OF ANY KIND, express or implied.
Classic Monitor is NOT a product of Midnite solar, nor do they support this application!

When it comes time to run the program, there are parameters that can be set or passed they are:  
**Parameters:**  
```  
--classic_name <classic>          : The name of your classic (used to subscribe to the coorect subject). 
--mqtt <mosquitto>                : The IP or URL of the MQTT Broker, defaults to mosquitto if unspecified.  
--mqtt_port <1883>                : The port for the MQTT Broker, defaults to 1883 if unspecified.  
--mqtt_root <ClassicMQTT>         : The root for your MQTT topics, defaults to ClassicMQTT if unspecified.  
--mqtt_user <ClassicClient>       : The username to access the MQTT Broker.  
--mqtt_pass <ClassicClient123>    : The passowrd to access the MQTT Broker.
--file <./client_output_file.txt> : The path and name of the file to write the data.
```  

## **Run It**

There are several ways to run this program:

1. **Standalone** - must have an MQTT server available and python 3 installed
2. **docker** - must have an MQTT server available and docker installed

### **1. Standalone**

Make sure that you have access to the MQTT server where the ClassicMQTT system is posting the data.  

1. Install Python 3.7 or newer and pip. Consult the documentation for your particular computer.
2. Install this library: **paho-mqtt** using pip:  
    ```
    pip install paho-mqtt
    ```   
3. Run the program from the command line where the classic_mqtt_client.py is located with the proper parameters:  
    ```
    python3 classic_mqtt_client.py --classic_name <Classic> --mqtt <127.0.0.1> --mqtt_root <ClassicMQTT> --mqtt_user <username> --mqtt_pass <password> --file ./client_data_output.txt
    ```
    **Example**:  
    If your Classic is named "Classic" and your mqtt server is Dioty, the settings would look something like this:  
    ```
    python3 classic_mqtt_client.py --classic_name Classic --mqtt mqtt.dioty.co --mqtt_root /joe.user@gmail.com/ClassicMQTT --mqtt_user joe.user@gmail.com --mqtt_pass <Joe's Dioty password> --file ./client_output_file.txt
    ```  

### **2. Using docker**

Using the "Dockerfile" in this directory will allow an image to be built so that a container can be run that runs the program. The Dockerfile uses a base image that already includes python and instructs it to install the needed library so you do not need to install python and pip, but you must install docker.  

1. Install docker on your host - look this up on the web and follow the instructions for your computer.
2. Issue the following command in this directory to build the docker image in the docker virtual environment (only need to do this once):
    ```
    docker build -t classic_mqtt_client .
    ```
3. Run the docker image and pass the parameters (substituing the correct values for parameter values):  
    ```
    docker run classic_mqtt_client --classic_name <Classic> --mqtt <127.0.0.1> --mqtt_port <1883> --mqtt_root <ClassicMQTT> --mqtt_user <username> --mqtt_pass <password> --file ./client_output_file.txt
    ```
4. For example, if your classic is named "classic" and your mqtt server is Dioty, the docker run command would look similar to this:  
    ```
    docker run classic_mqtt_client --classic_name classic --mqtt mqtt.dioty.co --mqtt_root /joe.user@gmail.com --mqtt_user joe.user@gmail.com --mqtt_pass <Joe's Dioty password> --file ./client_output_file.txt
    ```
5. For a real world example where connecting to the MQTT server that is running in the docker container created by the docker-compose in classic_mqtt you might use the following.
    ```
    sudo docker run --network python_localnet -e TZ=America/New_York -v /home/pi/classic_mqtt_client_files/:/files/ classic_mqtt_client --file /files/power_status.txt
    ```  
    Lets go over each of these:
    * **--network python_localnet** --> this tels the docker container to use the network that classic_mqtt and mosquitto are using as defined in their docker-compose file
    * **-e TZ=America/New_York** --> this passes an envronment variable into the container to get it to use the correct time zone.
    * **-v /home/pi/classic_mqtt_client_files/:/files/** --> this tells the container to use a volume so that when the tool writes out the file, it can be accessed by a program running on the host (and not in a container)
    * **classic_mqtt_client** --> the default parameters will work when connecting to classic_mqtt started from docker-compose.
    * **--file /files/power_status.txt** --> this parameter tells the client to write the file out to /files/power_status.txt and since /files is mapped to the /home/pi/classic_mqtt_client_files directory by the -v, the file will appear there when written in the container.