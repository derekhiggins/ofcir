import logging
import kopf
import kubernetes
import pprint

from flask import Flask, jsonify

import handlers

app = Flask(__name__)
kubernetes.config.load_incluster_config()
#kubernetes.config.load_kube_config()

logger = logging.getLogger("").setLevel(logging.INFO)
logger = logging.getLogger("ofcir")

@app.route('/ofcir', methods=['GET'])
def aquire_cir():
    api = kubernetes.client.CustomObjectsApi()

    custom_objects = api.list_namespaced_custom_object(group="metal3.io", version="v1", namespace="openshift-machine-api", plural="ciresources")
    # The return value from list_namespa... is a weird nested structure
    custom_objects = list(custom_objects.items())[1][1]
    rv = {}
    for custom_object in custom_objects:
        # todo lock
        obj = custom_object
        if obj["status"]["state"] != "available":
            continue
        obj["status"]["state"] = "inuse"
        try:
            api_response = api.replace_namespaced_custom_object( group="metal3.io", version="v1", namespace="openshift-machine-api", plural="ciresources", name=obj["metadata"]["name"], body=obj)
            break
        except:
            logger.info("Failed to get resource")
    else:
        return rv
    rv["ip"] = obj["status"]["address"]
    rv["name"] = obj["metadata"]["name"]
    return jsonify(rv)

@app.route('/ofcir/<name>', methods=['DELETE'])
def delete_cir(name):
    api = kubernetes.client.CustomObjectsApi()

    obj = handlers.getObject(name)
    obj["status"]["state"] = "cleaning"
    handlers.saveObject(obj)
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
