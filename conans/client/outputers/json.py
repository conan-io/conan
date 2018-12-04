# coding=utf-8

from conans.client.outputers.formats import OutputerFormats


@OutputerFormats.register("json")
class JSONOutputer(object):

    def __init__(self):
        pass


