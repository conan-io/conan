# coding=utf-8
from conans.client.output import Color
from conans.client.outputers.base_outputer import BaseOutputer
from conans.client.outputers.formats import OutputerFormats


@OutputerFormats.register("cli")
class CLIOutputer(BaseOutputer):

    def search(self, info, out, *args, **kwargs):
        results = info["results"]
        for remote_info in results:
            source = "cache" if remote_info["remote"] is None else str(remote_info["remote"])
            out.writeln("source: {}".format(source), Color.BRIGHT_WHITE)
            for conan_item in remote_info["items"]:
                reference = conan_item["recipe"]["id"]
                out.writeln("  {}".format(reference))
