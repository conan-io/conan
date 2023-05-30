import os

from conan.api.output import cli_out_write
from conan.cli.command import conan_command
from conan.cli.formatters import default_json_formatter
from conan import conan_version
import platform
import sys


def version_text_formatter(versions, root=None):
    for key, value in versions.items():
        if isinstance(value, dict):
            version_text_formatter(value, root=key)
        else:
            key = f"{root}.{key}" if root else key
            cli_out_write(f"{key}: {value}")


@conan_command(group="Consumer", formatters={"text": version_text_formatter, "json": default_json_formatter})
def version(conan_api, parser, *args):
    """
    Give information about the Conan client version.
    """

    return {'version': str(conan_version),
            'python': {
                'version': platform.python_version(),
                'sys_version': sys.version,
                }
            }

