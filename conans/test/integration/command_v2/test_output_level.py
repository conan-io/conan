import json

from conan.api.conan_api import ConanAPI, set_conan_output_level
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.tools import TestClient, redirect_output


def test_invalid_output_level():
    t = TestClient()
    t.save({"conanfile.py": GenConanfile()})
    t.run("create . --name foo --version 1.0 -vfooling", assert_error=True)
    assert "Invalid argument '-vfooling'"


def test_output_level():

    lines = ("self.output.trace('This is a trace')",
             "self.output.debug('This is a debug')",
             "self.output.verbose('This is a verbose')",
             "self.output.info('This is a info')",
             "self.output.highlight('This is a highlight')",
             "self.output.success('This is a success')",
             "self.output.warning('This is a warning')",
             "self.output.error('This is a error')",
             )

    t = TestClient()
    t.save({"conanfile.py": GenConanfile().with_package(*lines)})

    # By default, it prints > info
    t.run("create . --name foo --version 1.0")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" not in t.out
    assert "This is a info" in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # Print also verbose traces
    t.run("create . --name foo --version 1.0 -v")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" in t.out
    assert "This is a info" in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # Print also verbose traces
    t.run("create . --name foo --version 1.0 -vverbose")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" in t.out
    assert "This is a info" in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # Print also debug traces
    t.run("create . --name foo --version 1.0 -vv")
    assert "This is a trace" not in t.out
    assert "This is a debug" in t.out
    assert "This is a verbose" in t.out
    assert "This is a info" in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out
    t.run("create . --name foo --version 1.0 -vdebug")
    assert "This is a trace" not in t.out
    assert "This is a debug" in t.out
    assert "This is a verbose" in t.out
    assert "This is a info" in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # Print also "trace" traces
    t.run("create . --name foo --version 1.0 -vvv")
    assert "This is a trace" in t.out
    assert "This is a debug" in t.out
    assert "This is a verbose" in t.out
    assert "This is a info" in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out
    t.run("create . --name foo --version 1.0 -vtrace")
    assert "This is a trace" in t.out
    assert "This is a debug" in t.out
    assert "This is a verbose" in t.out
    assert "This is a info" in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # With notice
    t.run("create . --name foo --version 1.0 -vstatus")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" not in t.out
    assert "This is a info" in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # With notice
    t.run("create . --name foo --version 1.0 -vnotice")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" not in t.out
    assert "This is a info" not in t.out
    assert "This is a highlight" in t.out
    assert "This is a success" in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # With warnings
    t.run("create . --name foo --version 1.0 -vwarning")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" not in t.out
    assert "This is a info" not in t.out
    assert "This is a highlight" not in t.out
    assert "This is a success" not in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # With errors
    t.run("create . --name foo --version 1.0 -verror")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" not in t.out
    assert "This is a info" not in t.out
    assert "This is a highlight" not in t.out
    assert "This is a success" not in t.out
    assert "This is a warning" not in t.out
    assert "This is a error" in t.out


def test_logger_output_format():
    t = TestClient()
    t.save({"conanfile.py": GenConanfile()})

    # By default, it prints > info
    t.run("create . --name foo --version 1.0 --logger -vvv")
    lines = t.out.splitlines()
    for line in lines:
        data = json.loads(line)
        assert "json" in data
        assert "level" in data["json"]
        assert "time" in data["json"]
        assert "data" in data["json"]
        if data["json"]["level"] == "TRACE":
            assert "_action" in data["json"]["data"]


def test_python_api_log_change():
    t = TestClient()
    t.save({"conanfile.py": GenConanfile()})
    t.run("create . --name foo --version 1.0")

    stderr = RedirectedTestOutput()
    stdout = RedirectedTestOutput()
    with redirect_output(stderr, stdout):
        set_conan_output_level(10)
        api = ConanAPI(cache_folder=t.cache_folder)
        api.remotes.list()
        assert "_action: CONAN_API, name: remotes.list, parameters" in stderr

    stderr = RedirectedTestOutput()
    stdout = RedirectedTestOutput()
    with redirect_output(stderr, stdout):
        set_conan_output_level(20)
        api = ConanAPI(cache_folder=t.cache_folder)
        api.remotes.list()
        assert "_action: CONAN_API, name: remotes.list, parameters" not in stderr

    stderr = RedirectedTestOutput()
    stdout = RedirectedTestOutput()
    with redirect_output(stderr, stdout):
        set_conan_output_level(10, activate_logger=True)
        api = ConanAPI(cache_folder=t.cache_folder)
        api.remotes.list()
        assert "_action: CONAN_API, name: remotes.list, parameters" not in stderr
        assert '{"json": ' in stderr
