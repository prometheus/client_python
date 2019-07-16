import os


class Pidprovider(object):
    source = os.getpid

    @classmethod
    def getpid(cls):
        return cls.source()
