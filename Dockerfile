FROM quay.io/bitnami/python:3.7

RUN curl -fsSL https://clis.cloud.ibm.com/install/linux | sh

RUN pip install kopf kubernetes packet-python flask
COPY ofcir /app
