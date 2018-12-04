# coding=utf-8

import json

from conans.util.files import save
from conans.client.outputers.base_outputer import BaseOutputer
from conans.client.outputers.formats import OutputerFormats


def _date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


@OutputerFormats.register("json")
class JSONOutputer(BaseOutputer):

    def _save_output(self, info, output_filepath, out, *args, **kwargs):
        save(output_filepath, json.dumps(info, default=_date_handler))
        out.writeln("")
        out.info("JSON file created at '{}'".format(output_filepath))

    def search_recipes(self, *args, **kwargs):
        self._save_output(*args, **kwargs)

    def search_packages(self, *args, **kwargs):
        self._save_output(*args, **kwargs)
