import json
import logging
import random
import socket
import time

import ironicclient

from . import Base, ProviderException

logger = logging.getLogger("ofcir.ironic")

cdstr={"meta_data": {"public_keys": {"0": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDuQAJLlOQ8jVIsjspcpuqteZN27TEctPxwRaLvamVyEiqHrBtcVAEk42/u0CqdX1n0ki4Le/+NSDfkz6XZG6jgO+YVjq2+qjpklRPIf/plFbmTggMf3a2RQ/H+34aM+Dx8AbS9o27FX6HjYL/dZDr6OaUJUTXV/fea+XgGCoFxI4YEuiiJJoOMvQkMNXXfSOWTVvClWHGDXVgfdc00u1uAA3PRxgD06Xl5tvAPGzIDlrgEBB4qvwTim/b4D1Lf4q+aDnDzlgsoSL5oDbwdAjuylMbo5tzNe8XzxWBOj91cCWHswToU0St2FqZR7E7uRUMSn05SyzKWfw61pyAFEbocKQ3uuD3vrL9CkQOer8dO79fE5ihEmCO8ZPRHjNaUR7XJ/bDgromqmMMJ5fnLsOab0gfRCXySERtOkYajls3n0ekjzXUfknZSTlI9yJ9OPzrBUygM1s6+yiKwPVCXRz0ljMqjHtPK69wKT1Mt6IV/fIC5MKoeG1Zh2uuSFYLmYjE= ofcirkey"}}}

class Ironic(Base):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.ironic_endpoint = kwargs["ironic_endpoint"]
        self.ironic_user = kwargs["ironic_user"]
        self.ironic_password = kwargs["ironic_password"]

        self.ironic = ironicclient.client.get_client(
            1, os_ironic_api_version="1.78", endpoint=self.ironic_endpoint,
            name=self.ironic_user, password=self.ironic_password
        )

    def clean(self, obj):
        name=obj["metadata"]["name"]
        logger.info('cleaning %s'%name)

        provider_info = obj["spec"].get("provider_info")
        if not provider_info:
            msg="Missing provider_info %s"%name
            logger.warn(msg)
            raise ProviderException(msg)

        info = json.loads(provider_info)

        node=self.ironic.node.get(info["id"])
        ip = node.extra["ip"]
        obj["status"]["address"] = ip


        if node.provision_state not in ["cleaning", "clean wait", "available"]:
            self.ironic.node.update(info["id"], [{"op":"add", "path":"/instance_info", "value":{"image_source":"http://10.10.129.10:8080/images/CentOS-Stream-GenericCloud-8-20220125.1.x86_64.qcow2", "image_checksum":"http://10.10.129.10:8080/images/CentOS-Stream-GenericCloud-8-20220125.1.x86_64.qcow2.md5sum"}}])
            self.ironic.node.set_provision_state(info["id"], "rebuild", configdrive=cdstr)
            time.sleep(60*7) # reinstall takes over 7 minutes

        self._wait_active(info["id"])

    def aquire(self, obj):
        name=obj["metadata"]["name"]
        logger.info('aquiring %s'%name)
        
        provider_info = obj["spec"].get("provider_info", "{}")
        info = json.loads(provider_info)

        for node in self.ironic.node.list():
            if name == node.name:
                logger.info('Found node %s %s, state=%s'%(node.name, node.uuid, node.provision_state))
                if node.provision_state in [ "available", "active"]:
                    self.ironic.node.update(node.uuid, [{"op":"add", "path":"/instance_info", "value":{"image_source":"http://10.10.129.10:8080/images/CentOS-Stream-GenericCloud-8-20220125.1.x86_64.qcow2", "image_checksum":"http://10.10.129.10:8080/images/CentOS-Stream-GenericCloud-8-20220125.1.x86_64.qcow2.md5sum"}}])
                    newstate = "active"
                    if node.provision_state == "active":
                        newstate = "rebuild"
                    self.ironic.node.set_provision_state(node.uuid, newstate, configdrive=cdstr)
                    break
        else:
            msg="Failed to find a active/available node to aquire %s"%name
            logger.warn(msg)
            raise ProviderException(msg)
            
        info["id"] = node.uuid

        node = self._wait_active(info["id"])

        ip = node.extra["ip"]
        obj["status"]["address"] = ip
        obj["spec"]["provider_info"] = json.dumps(info)

    def release(self, obj):
        name=obj["metadata"]["name"]
        logger.info('releasing %s'%name)
        
        provider_info = obj["spec"].get("provider_info")
        if not provider_info:
            msg="Missing provider_info %s"%name
            logger.warn(msg)
            raise ProviderException(msg)

        info = json.loads(provider_info)
        self.ironic.node.set_provision_state(info["id"], "clean")
        obj["status"]["address"] = ''

    def _wait_active(self, device_id, i=30):
        c=0
        while True:
            c=c+1
            node = self.ironic.node.get(device_id)
            logger.info('Device %s, State %s'%(node.name, node.provision_state))
            if node.provision_state == "active":
                break
            if c > i:
                msg="Node not going Active %s"%node.name
                logger.warn(msg)
                raise ProviderException(msg)
            time.sleep(30)

        c=0
        while True:
            c=c+1
            ip = node.extra["ip"]
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            logger.info('Testing ssh %r'%(node.name))
            if sock.connect_ex((ip, 22)) == 0:
                return node
            if c > 30:
                # Nodes where this happens don't tend to recover
                # delete it so a new one will be created
                msg="Node has no ssh port open"%node.name
                logger.warn(msg)
                # Set the status.state backt to registered so we acquire a new node
                raise ProviderException(msg, 'registered')
            time.sleep(30)
