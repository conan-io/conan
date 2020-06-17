import json

from conans.client.formatters.base_formatter import BaseFormatter
from conans.client.output import Color


class DigFormatter(BaseFormatter):

    @classmethod
    def cli(cls, info, out):
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

    @classmethod
    def json(cls, info, out):
        myjson = json.dumps(info, indent=4)
        out.writeln(myjson)
