#! /bin/bash

#set the ENV variables that the script uses
export LOGFILE="/home/pi/classic_mqtt.log"
export LOGLEVEL=DEBUG

#This will check and make sure at least one copy of the classic_mqtt.py script
#is running. If there is one, it does nothing and exits, if there is'nt one, it will spawn one and make a log entry and exit.
#If there is more than 1, it will kill off all but one, make log enties and exit. 
#It can be used in cron to make sure that the script keeps running.
#
# Be sure to replace: 
#    <classic ip or hostname> with your Classic
#    <username> with your MQTT username
#    <password> with your password
#
#An entry in cron to run this every minute might look like this:
#* * * * * /home/pi/check_run_classic.sh

#pidof only works in this case if you can start the script with "./classic_mqtt.py ...". So you must make the script
#executable with chmod +x classic_mqtt.py. Also on the Raspberry Pi the first line of the script needs to point to the actual location
#of python3. In the Raspberry Pi environment this is #!/usr/bin/python3. In other systems it may be different.
case "$(pidof -x classic_mqtt.py | wc -w)" in

0)  echo "Restarting classic_mqtt:     $(date)" >> /home/pi/classic_mqtt_run.log
    ./classic_mqtt.py --classic <classic ip or hostname>  --mqtt_root ClassicMQTT --user <userrname> --pass <password>&
    ;;
1)  # all ok, do nothing
    ;;
*)  echo "Removed double classic_mqtt: $(date)" >> /home/pi/classic_mqtt_run.log
    kill $(pidof -x classic_mqtt.py | awk '{print $1}')
    ;;
esac

