class StreamBotException(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class LockedDropletException(StreamBotException):
    def __init__(self, *args, **kwargs):
        StreamBotException.__init__(self, *args, **kwargs)


class MissingSnapshotException(StreamBotException):
    def __init__(self, *args, **kwargs):
        StreamBotException.__init__(self, *args, **kwargs)


class MissingFirewallException(StreamBotException):
    def __init__(self, *args, **kwargs):
        StreamBotException.__init__(self, *args, **kwargs)


class MissingDropletException(StreamBotException):
    def __init__(self, *args, **kwargs):
        StreamBotException.__init__(self, *args, **kwargs)


class DropletBootFailedException(StreamBotException):
    def __init__(self, *args, **kwargs):
        StreamBotException.__init__(self, *args, **kwargs)


class UnauthorizedUserException(StreamBotException):
    def __init__(self, *args, **kwargs):
        StreamBotException.__init__(self, *args, **kwargs)