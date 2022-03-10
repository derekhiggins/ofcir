
from . import Base
import logging
logger = logging.getLogger("ofcir")

class Dummy(Base):
    def __init__(self, *args, **kwargs):
        super().__init__()
    def clean(self, obj):
        name=obj["metadata"]["name"]
        logger.info('cleaning %s'%name)

    def aquire(self, obj):
        name=obj["metadata"]["name"]
        logger.info('aquiring %s'%name)
        
        obj["status"]["address"] = '1.2.3.4'

    def release(self, obj):
        name=obj["metadata"]["name"]
        logger.info('releasing %s'%name)
        
