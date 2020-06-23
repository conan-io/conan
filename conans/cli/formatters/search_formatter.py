import json

from conans.cli.formatters.base_formatter import BaseFormatter
from conans.client.output import Color


class SearchFormatter(BaseFormatter):

    @classmethod
    def cli(cls, info, out):
        results = info["results"]
        for remote_info in results:
            source = "cache" if remote_info["remote"] is None else str(remote_info["remote"])
            out.writeln("{}:".format(source), Color.BRIGHT_WHITE)
            for conan_item in remote_info["items"]:
                reference = conan_item["recipe"]["id"]
                out.writeln(" {}".format(reference))

    @classmethod
    def json(cls, info, out):
        myjson = json.dumps(info, indent=4)
        out.writeln(myjson)
