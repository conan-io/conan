# coding=utf-8
from conans.client.output import Color
from conans.client.formatters.base_formatter import BaseFormatter
from conans.client.formatters.formats import FormatterFormats


@FormatterFormats.register("cli")
class CLIFormatter(BaseFormatter):

    def search(self, info, out, *args, **kwargs):
        results = info["results"]
        for remote_info in results:
            source = "cache" if remote_info["remote"] is None else str(remote_info["remote"])
            out.writeln("{}:".format(source), Color.BRIGHT_WHITE)
            for conan_item in remote_info["items"]:
                reference = conan_item["recipe"]["id"]
                out.writeln("  {}".format(reference))
