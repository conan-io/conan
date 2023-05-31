from conan.cli.commands.list import print_serial
from conan.cli.command import conan_command
from conan.cli.formatters import default_json_formatter
from conan import conan_version
import platform
import sys


@conan_command(group="Consumer", formatters={"text": print_serial, "json": default_json_formatter})
def version(conan_api, parser, *args):
    """
    Give information about the Conan client version.
    """

    return {'version': str(conan_version),
            'python': {
                'version': platform.python_version().replace('\n', ''),
                'sys_version': sys.version.replace('\n', ''),
                }
            }

