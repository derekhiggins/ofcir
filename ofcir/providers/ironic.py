import json
import logging
import random
import socket
import time

import ironicclient

from . import Base, ProviderException

logger = logging.getLogger("ofcir.ironic")

cdstr={"meta_data": {"public_keys": {"0": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCuCKx7kbcLQ6CBdgy+UtkV48h8Sj/REluJlGQfg5ZQIa64oAxRExbtgLe8s6ThAT50FwhKagel3IjQbOwYr9cuCjuK2D70x9VeMWNOj6MZSA8/Rg0TWRuOWktmInX2gZMTxAb0L5b07q3e+dZJbij9ZrvEktcEtS54fuh2tQZjVhcySfefiwSFibFucmIGbj5xsg9AHxnlKDijomPC7I0BOHAFJ5ZXEhdVfQxLiBCqUmIU6dHMFh6lb9fHNkg79XbFcEbG3Ja7maXlHPhP+ev9oNazZRmoqEuEvJbT0KG3vIYAmYFxDlvyLJI8gw6BmueHjW1NQeLIjTI44NZCkLhBoqDEr5fjNnul7gzEcSXOTygCGu05OX8nkwG1Q9CyGn7RS8/wmDiK0gUK3ZMXHgXcWU2RNHQW+YDv2RzzVHEElsSC3Co1Rw/1nBKP3hCqno8EY8QwoWO78aRc5v/jdG1PaTLjUoer37T2vjRlOUItlIvgGp9+JWdw4fIzQtGiLrk="}}}

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
            image = node.extra["image"]
            self.ironic.node.update(node.uuid, [{"op":"add", "path":"/instance_info", "value":{"image_source":image, "image_checksum":image+".md5sum"}}])
            self.ironic.node.set_provision_state(info["id"], "rebuild", configdrive=cdstr)
            time.sleep(60*7) # reinstall takes over 7 minutes

        self._wait_active(info["id"])

    def aquire(self, obj):
        name=obj["metadata"]["name"]
        logger.info('aquiring %s'%name)

        provider_info = obj["spec"].get("provider_info", "{}")
        info = json.loads(provider_info)

        for node in self.ironic.node.list(fields=['uuid','extra','name','provision_state']):
            if name == node.name:
                logger.info('Found node %s %s, state=%s'%(node.name, node.uuid, node.provision_state))
                if node.provision_state in [ "available", "active"]:
                    image = node.extra["image"]
                    self.ironic.node.update(node.uuid, [{"op":"add", "path":"/instance_info", "value":{"image_source":image, "image_checksum":image+".md5sum"}}])
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
        node=self.ironic.node.get(info["id"])
        if node.provision_state == "active":
            self.ironic.node.set_provision_state(info["id"], "undeploy")
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
