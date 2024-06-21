from conan.api.conan_api import ConanAPI
from conan.cli.cli import Cli
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import redirect_output


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


def test_basic_api():
    api = ConanAPI(cache_folder=temp_folder())
    result = api.remotes.list()
    assert result[0].name == "conancenter"


def test_api_command():
    # The ``CommandAPI`` requires a bit more of setup
    api = ConanAPI(cache_folder=temp_folder())
    cli = Cli(api)
    cli.add_commands()
    result = api.command.run(["remote", "list"])
    assert result[0].name == "conancenter"
