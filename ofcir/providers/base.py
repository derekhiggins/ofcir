
class Base():
    def clean(self, obj):
        pass
    def aquire(self, obj):
        pass
    def release(self, obj):
        pass

class ProviderException(Exception):
    def __init__(self, message, state=None):
        super().__init__(message)
        self.state = state
