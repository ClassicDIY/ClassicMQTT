FROM python:3.7.6-slim-stretch

RUN pip install --no-cache-dir paho-mqtt

ADD classic_mqtt_client.py /
ADD classic_validate.py /

ENTRYPOINT ["python3", "classic_mqtt_client.py"]