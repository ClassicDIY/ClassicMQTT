FROM python:3.7.6-slim-stretch

RUN pip install --no-cache-dir pymodbus paho-mqtt timeloop

ADD classic_mqtt.py /
ADD support/*.py support/

ENTRYPOINT ["python3", "classic_mqtt.py"]