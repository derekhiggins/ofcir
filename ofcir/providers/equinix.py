import json
import time
import logging

import packet

from . import Base

logger = logging.getLogger("ofcir.equinix")

class Equinix(Base):
    def __init__(self, *args, **kwargs):
        super().__init__()

        self.apitoken = kwargs["equinix_apitoken"]
        self.project = kwargs["equinix_project"]

        self.manager = packet.Manager(auth_token=self.apitoken)

    def clean(self, obj):
        name=obj["metadata"]["name"]
        logger.info('cleaning %s'%name)

        provider_info = obj["spec"].get("provider_info")
        if not provider_info:
            msg="Missing provider_info "%name
            logger.warn(msg)
            raise Exception(msg)

        info = json.loads(provider_info)

        device = self.manager.get_device(info["id"])
        ip = device.ip_addresses[0]["address"]
        obj["status"]["address"] = ip
        if device.state not in ["reinstalling", "provisioning"]:
            device.reinstall()
            time.sleep(60*10) # reinstall takes over 10 minutes

        self._wait_active(info["id"])

    def aquire(self, obj):
        name=obj["metadata"]["name"]
        logger.info('aquiring %s'%name)
        
        provider_info = obj["spec"].get("provider_info", "{}")
        info = json.loads(provider_info)

        count = 0
        devicename = "cir-"+name
        for device in self.manager.list_all_devices(self.project):
            if devicename == device.hostname:
                #TODO: may want to consider cleaning this node...
                break
            if "cir-" in device.hostname:
                count = count + 1
        else:
            logger.info('Creating new node %s'% count)
            # TODO: remove safetly when we are sure this wont accidently create a gazillion BM servers
            if count > 5:
                logger.info('SAFETY: TOO MANY SERVERS: %s'%count)
                return

            device = self.manager.create_device(
                project_id = self.project,
                hostname = devicename,
                plan = "m3.large.x86",
                operating_system = "rocky_8",
                facility = "any"
            )
            time.sleep(60*10)

        info["id"] = device.id

        device = self._wait_active(info["id"])

        ip = device.ip_addresses[0]["address"]
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
        device = self.manager.get_device(info["id"])
        device.delete()

    def _wait_active(self, device_id):
        c=0
        while True:
            c=c+1
            device = self.manager.get_device(device_id)
            logger.debug('Device %s, State %s'%(device.hostname, device.state))
            if device.state == "active":
                return device
            if c > 60:
                msg="Node not going Active "%name
                logger.warn(msg)
                raise Exception(msg)
            time.sleep(30)
