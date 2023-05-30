import os

from conan.api.output import cli_out_write
from conan.cli.command import conan_command
from conan.cli.formatters import default_json_formatter
from conan import conan_version


def version_text_formatter(version):
    cli_out_write(f"Conan version {version['version']}")


@conan_command(group="Consumer", formatters={"text": version_text_formatter, "json": default_json_formatter})
def version(conan_api, parser, *args):
    """
    Give information about the Conan client version.
    """

    result = {'version': str(conan_version)}
    return result

