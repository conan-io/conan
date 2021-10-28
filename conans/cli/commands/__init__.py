import json

from conans.cli.output import cli_out_write


def json_formatter(data):
    myjson = json.dumps(data, indent=4)
    cli_out_write(myjson)
