FROM quay.io/bitnami/python:3.7
RUN pip install kopf kubernetes packet-python flask
COPY ofcir /app
