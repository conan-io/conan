# coding=utf-8

import json

from conans.client.formatters.base_formatter import BaseFormatter
from conans.client.formatters.formats import FormatterFormats


@FormatterFormats.register("json")
class JSONFormatter(BaseFormatter):

    def search(self, info, out, *args, **kwargs):
        myjson = json.dumps(info, indent=4)
        out.writeln(myjson)
