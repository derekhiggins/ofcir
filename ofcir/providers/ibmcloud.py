import json
import time
import logging
import random
import subprocess

from . import Base

logger = logging.getLogger("ofcir.ibmcloud")

def ibmcloud(cmd, json_out=True):
    cmd = ["ibmcloud"]+cmd
    if json_out:
        cmd = cmd+["--output", "JSON"]
    try:
        data = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, check=True).stdout
    except subprocess.CalledProcessError as E:
        logger.error('Error running ibmcloud command: %r'%(cmd))
        raise
    if json_out:
        return json.loads(data)


class IBMCloud(Base):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def clean(self, obj):
        name=obj["metadata"]["name"]
        logger.info('cleaning %s'%name)

        provider_info = obj["spec"].get("provider_info")
        if not provider_info:
            msg="Missing provider_info %s"%name
            logger.warn(msg)
            raise Exception(msg)

        info = json.loads(provider_info)

        device = ibmcloud(["sl", "hardware", "detail", info["id"]])
        ip = device["primaryIpAddress"]
        obj["status"]["address"] = ip
        logger.debug('%s status is %s'%(name, device["hardwareStatus"]["status"]))
        if device["hardwareStatus"]["status"] not in ["DEPLOY", "DEPLOY2"]:
            ibmcloud(["sl", "hardware", "reload", "-f", "--key", "2139952", info["id"]], json_out=False)
            time.sleep(60*7) # reinstall takes over 7 minutes
        self._wait_active(info["id"])

    def aquire(self, obj):
        name=obj["metadata"]["name"]
        logger.info('aquiring %s'%name)

        provider_info = obj["spec"].get("provider_info", "{}")
        info = json.loads(provider_info)

        count = 0
        devicename = "cir-"+name
        for device in ibmcloud(["sl", "hardware", "list"]):
            if devicename == device["hostname"]:
                #TODO: may want to consider cleaning this node...
                logger.info('Aquired existing node %s %d'%(device["hostname"], device["id"]))
                break
            if "cir-" in device["hostname"]:
                count = count + 1
        else:
            logger.debug('Creating new node %s (%s)'%(devicename, count))
            # TODO: Do something, has to be manual currently
            raise(Exception("Can't create nodes"))

        info["id"] = str(device["id"])

        device = self._wait_active(info["id"])

        ip = device["primaryIpAddress"]
        obj["status"]["address"] = ip
        obj["spec"]["provider_info"] = json.dumps(info)

    def release(self, obj):
        name=obj["metadata"]["name"]
        logger.info('releasing %s'%name)

        provider_info = obj["spec"].get("provider_info")
        if not provider_info:
            msg="Missing provider_info "%name
            logger.warn(msg)
            raise Exception(msg)

        info = json.loads(provider_info)
        # TODO: Do something
        obj["status"]["address"] = ''

    def _wait_active(self, device_id, i=60):
        c=0
        while True:
            c=c+1
            device = ibmcloud(["sl", "hardware", "detail", device_id])
            logger.info('Device %s, State %s'%(device["hostname"], device["hardwareStatus"]["status"]))
            if device["hardwareStatus"]["status"] == "ACTIVE":
                return device
            if c > i:
                msg="Node not going Active %s"%device["hostname"]
                logger.warn(msg)
                raise Exception(msg)
            time.sleep(30)
