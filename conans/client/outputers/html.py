# coding=utf-8

from conans.client.outputers.base_outputer import BaseOutputer
from conans.client.outputers.formats import OutputerFormats


@OutputerFormats.register("html")
class HTMLOutputer(BaseOutputer):

    def __init__(self):
        pass


