# coding=utf-8

import json

from conans.client.outputers.base_outputer import BaseOutputer
from conans.client.outputers.formats import OutputerFormats


@OutputerFormats.register("json")
class JSONOutputer(BaseOutputer):
    def search(self, *args, **kwargs):
        pass
