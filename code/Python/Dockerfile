FROM python:3.9.19-slim

RUN pip install --no-cache-dir pymodbus paho-mqtt

ADD classic_mqtt.py /
ADD support/*.py support/

ENTRYPOINT ["python3", "classic_mqtt.py"]
