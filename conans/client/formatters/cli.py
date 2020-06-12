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
                out.writeln(" {}".format(reference))

    def dig(self, info, out, *args, **kwargs):
        results = info["results"]
        for remote_info in results:
            source = "cache" if remote_info["remote"] is None else str(remote_info["remote"])
            out.writeln("{}:".format(source), Color.BRIGHT_WHITE)
            for conan_item in remote_info["items"]:
                reference = conan_item["recipe"]["id"]
                out.writeln(" {}".format(reference), Color.BRIGHT_GREEN)
                for package in conan_item["packages"]:
                    out.writeln(" :{}".format(package["id"]), Color.BRIGHT_GREEN)
                    out.writeln("  [options]", Color.BRIGHT_WHITE)
                    for option, value in package["options"].items():
                        out.write("  {}: ".format(option), Color.YELLOW)
                        out.write("{}".format(value), newline=True)
                    out.writeln("  [settings]", Color.BRIGHT_WHITE)
                    for setting, value in package["settings"].items():
                        out.write("  {}: ".format(setting), Color.YELLOW)
                        out.write("{}".format(value), newline=True)

