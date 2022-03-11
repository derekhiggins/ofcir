#!/bin/bash

set -ex

cd $(dirname $0)

podman build -f Dockerfile -t testyimage:op
podman push --authfile /opt/dev-scripts/pull_secret.json localhost/testyimage:op virthost.ostest.test.metalkube.org:5000/localimages/testimage:op
oc get project ofcir || oc new-project ofcir
oc -n ofcir delete --grace-period=1 pod/operator || true
oc -n ofcir apply -f deploy.yaml


