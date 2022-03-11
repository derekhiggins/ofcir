import json
import base64
import logging
import time

import kopf
import kubernetes

import providers

logging.getLogger("").setLevel(logging.INFO)
logger = logging.getLogger("ofcir")

def getObject(name):
    api = kubernetes.client.CustomObjectsApi()
    obj = api.get_namespaced_custom_object(group="metal3.io", version="v1", namespace="ofcir", plural="ciresources", name=name)
    return obj
def saveObject(obj):
    api = kubernetes.client.CustomObjectsApi()
    obj["status"]["lastUpdated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    api_response = api.replace_namespaced_custom_object( group="metal3.io", version="v1", namespace="ofcir", plural="ciresources", name=obj["metadata"]["name"], body=obj)


secrets={}
@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.posting.level = logging.INFO

    kubernetes.config.load_incluster_config()
    v1 = kubernetes.client.CoreV1Api()
    secret = v1.read_namespaced_secret("ofcir-secrets", "ofcir")

    for k,v in secret.data.items():
        secrets[k] = base64.b64decode(v).decode()

@kopf.on.delete('metal3.io', 'v1', 'ciresource')
def delete_fn(name, spec, **kwargs):
    obj = getObject(name)
    provider = eval("providers."+spec['provider'])(**secrets)
    for _ in range(10):
        try:
            logger.info('deleting %r'%(name))
            provider.release(obj)
            return
        except:
            time.sleep(10)
    logger.info('failed deleting %r'%(name))

@kopf.daemon('ciresource',
    when=lambda spec, status, **_: spec.get("state") != status.get("state")
)
def resolve(stopped, name, meta, spec, status, **kwargs):
    provider = eval("providers."+spec['provider'])(**secrets)
    first = True
    while True:

        # stopped is update live when this loop should finish, but there is a short delay
        # wait 1 second to avoid doing a iteration of the loop when not needed
        time.sleep(1)
        if stopped: break
        if not first:
            time.sleep(10)
        first = False
        if stopped: break

        # Save the resourceVersion, if we try to save the object after its been elsewhere
        # changed then the replace will fail (using replace vs patch)
        resourceVersion = meta["resourceVersion"]
        action = None
        if spec["state"] == "registered":
            if status["state"] in ["inuse", "error"]:
                continue
            elif status["state"] == "cleaning":
                action = provider.clean
            elif status["state"] in ["idle", "available"]:
                action = provider.release
        elif spec["state"] == "idle":
            if status["state"] in ["inuse", "error"]:
                continue
            elif status["state"] == "cleaning":
                action = provider.clean
            elif status["state"] in "registered":
                action = provider.aquire
        elif spec["state"] == "available":
            if status["state"] in ["inuse", "error"]:
                continue
            elif status["state"] in ["idle", "cleaning"]:
                action = provider.clean
            elif status["state"] in "registered":
                action = provider.aquire

        logger.info('resolving %r'%(name))
        try:
            obj = getObject(name)
            obj["metadata"]["resourceVersion"] = resourceVersion
            try:
                if action:
                    action(obj)
                obj["status"]["state"] = spec["state"]
                obj["status"]["message"] = ""
            except Exception as e:
                # TODO: revist how the error state works
                # Lets not do this yet so that a retry isn't ignored
                #obj["status"]["state"] = "error"
                obj["status"]["message"] = repr(e.args)
                logger.error('resolve error %r, %r'%(name, e))
            saveObject(obj)
        except Exception as e:
            logger.error('CRD api error %r, %r'%(name, e))

# Releases a resource if it is more then X hours "inuse"
@kopf.timer('ciresource', idle=60*60*3, interval=6,
    when=lambda spec, status, **_: status.get("state") == "inuse"
)
def release(stopped, name, meta, spec, status, **kwargs):
    if status["state"] == "inuse":
        logger.info('releasing forgotten cir %r'%(name))
        obj = getObject(name)
        obj["status"]["state"] = "cleaning"
        obj["status"]["message"] = ""
        saveObject(obj)
