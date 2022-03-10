#!/bin/bash

set -ex

cd $(dirname $0)

podman build -f Dockerfile -t testyimage:op
podman push --authfile /opt/dev-scripts/pull_secret.json localhost/testyimage:op virthost.ostest.test.metalkube.org:5000/localimages/testimage:op
oc -n openshift-machine-api delete --grace-period=1 pod/operator || true
oc -n openshift-machine-api apply -f deploy.yaml


