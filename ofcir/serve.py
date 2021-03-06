import logging
import kopf
import kubernetes
import random

from flask import Flask, jsonify, abort, request

import handlers

app = Flask(__name__)
kubernetes.config.load_incluster_config()
#kubernetes.config.load_kube_config()

@app.route('/ofcir', methods=['POST'])
def aquire_cir():
    api = kubernetes.client.CustomObjectsApi()

    cirtype = request.args.get('type', 'cihost')

    # using field sectors here would be great
    custom_objects = api.list_namespaced_custom_object(group="metal3.io", version="v1", namespace="ofcir", plural="ciresources")
    # The return value from list_namespa... is a weird nested structure
    custom_objects = list(custom_objects.items())[1][1]
    rv = {}
    random.shuffle(custom_objects)
    for custom_object in custom_objects:
        obj = custom_object
        if obj["status"]["state"] != "available":
            continue
        if obj["spec"]["type"] != cirtype:
            continue
        obj["status"]["state"] = "inuse"
        try:
            # This should fail if another request grabs this host before us (replace vs patch)
            handlers.saveObject(obj)
            break
        except:
            app.logger.debug("Failed to get resource")
    else:
        # 409 Conflict: request conflicts with the current state of the server
        abort(409)
    app.logger.debug("Aquiring CIR %s"%obj["metadata"]["name"])
    rv["ip"] = obj["status"]["address"]
    rv["name"] = obj["metadata"]["name"]
    rv["extra"] = obj["spec"]["extra"]
    return jsonify(rv)

@app.route('/ofcir/<name>', methods=['DELETE'])
def delete_cir(name):
    try:
        obj = handlers.getObject(name)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            abort(404)
        else:
            app.logger.error("Problem Freeing CIR %s"%str(e))
        abort(e.status)
    if obj["status"]["state"] != "inuse":
        abort(409)
    obj["status"]["state"] = "cleaning"
    handlers.saveObject(obj)
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
