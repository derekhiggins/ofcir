
from . import Base
import logging
import time

logger = logging.getLogger("ofcir.dummy")

class Dummy(Base):
    def __init__(self, *args, **kwargs):
        super().__init__()
    def clean(self, obj):
        name=obj["metadata"]["name"]
        logger.info('cleaning %s'%name)
        time.sleep(10)

    def aquire(self, obj):
        name=obj["metadata"]["name"]
        logger.info('aquiring %s'%name)
        
        obj["status"]["address"] = '1.2.3.4'
        time.sleep(10)

    def release(self, obj):
        name=obj["metadata"]["name"]
        obj["status"]["address"] = ''
        logger.info('releasing %s'%name)
        
