from conan.api.conan_api import ConanAPI
from conan.cli.cli import Cli
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import redirect_output


def test_cli():
    """ make sure the CLi can be reused
    https://github.com/conan-io/conan/issues/14044
    """
    folder = temp_folder()
    api = ConanAPI(cache_folder=folder)
    cli = Cli(api)
    cli2 = Cli(api)

    stdout = RedirectedTestOutput()
    stderr = RedirectedTestOutput()
    with redirect_output(stderr, stdout):
        cli.run(["list", "*"])
        cli.run(["list", "*"])
        cli2.run(["list", "*"])
        cli.run(["list", "*"])
