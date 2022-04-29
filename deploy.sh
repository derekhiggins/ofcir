#!/bin/bash

set -ex

cd $(dirname $0)

podman build -f Dockerfile -t ofcirimage:lastest
podman push --authfile /opt/dev-scripts/pull_secret.json localhost/ofcirimage:lastest virthost.ostest.test.metalkube.org:5000/localimages/testimage:op
oc get project ofcir || oc new-project ofcir

DATE=$(date +%s)
oc logs ofcir -c operator > logs/operator.${DATE}.log || true
oc logs ofcir -c serve > logs/serve.${DATE}.log || true


oc -n ofcir delete --grace-period=1 pod/ofcir || true
oc -n ofcir apply -f deploy.yaml


