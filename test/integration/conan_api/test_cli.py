import os

import pytest

from conan.api.conan_api import ConanAPI
from conan.cli.cli import Cli, main
from conan.errors import ConanException
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.env import environment_update
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import redirect_output, TestClient


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

    stdout = RedirectedTestOutput()
    stderr = RedirectedTestOutput()
    with redirect_output(stderr, stdout):
        cli.run()
    # Running without args shows help, but doesn't error
    assert "Consumer commands" in stdout.getvalue()


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


@pytest.mark.parametrize("raise_on_errors", [True, False])
def test_api_command_error(raise_on_errors):
    """ ``conan_api.command.run()`` does NOT raise a build/install error by itself: "create"/
    "install" defer it into a "conan_error" entry of their result instead of raising directly
    (so formatters can still run, e.g. to write "graph.json" on failure, see #19204). It is the
    caller's responsibility to check the result and raise/report it if desired, as documented
    in this method's docstring. See https://github.com/conan-io/conan/issues/20258, where
    "workspace create"/"workspace install" needed to start doing exactly that, since they
    chain commands via this API and a failure in one must stop the rest.
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_package("raise Exception('boom')")})
    c.run("export .")
    if raise_on_errors:
        with pytest.raises(ConanException) as e:
            c.api.command.run(["create", c.current_folder], raise_on_errors=raise_on_errors)
        assert "boom" in str(e.value)
    else:
        result = c.api.command.run(["create", c.current_folder], raise_on_errors=raise_on_errors)
        assert isinstance(result["conan_error"], ConanException)
        assert "boom" in str(result["conan_error"])


def test_main():
    cache_folder = os.path.join(temp_folder(), "custom")
    with environment_update({"CONAN_HOME": cache_folder}):
        with pytest.raises(SystemExit) as e:
            main(["list", "*"])
        assert e.type == SystemExit
        assert e.value.code == 0  # success
