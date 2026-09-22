import json
import os
import textwrap

import pytest

from conan.internal.util.files import save
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.test.utils.env import environment_update


class TestOutputLevel:
    def test_invalid_output_level(self):
        t = TestClient(light=True)
        t.save({"conanfile.py": GenConanfile("foo", "1.0")})
        t.run("create . -vfooling", assert_error=True)
        assert "argument -v: invalid choice: 'fooling'" in t.out

        with environment_update({"CONAN_LOG_LEVEL": "fail"}):
            t.run("create .", assert_error=True)
            assert "Invalid argument '-vfail' defined in CONAN_LOG_LEVEL " \
                   "environment variable" in t.out

    def test_output_level(self):
        lines = ("self.output.trace('This is a trace')",
                 "self.output.debug('This is a debug')",
                 "self.output.verbose('This is a verbose')",
                 "self.output.info('This is a info')",
                 "self.output.highlight('This is a highlight')",
                 "self.output.success('This is a success')",
                 "self.output.warning('This is a warning')",
                 "self.output.error('This is a error')",
                 )

        t = TestClient(light=True)
        t.save({"conanfile.py": GenConanfile("foo", "1.0").with_package(*lines)})

        # By default, it prints > info
        t.run("create .")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" not in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # Check if -v argument is equal to VERBOSE level
        t.run("create . -v")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # Print also verbose traces
        t.run("create . -vverbose")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # Print also debug traces
        t.run("create . -vv")
        assert "This is a trace" not in t.out
        assert "This is a debug" in t.out
        assert "This is a verbose" in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out
        t.run("create . -vdebug")
        assert "This is a trace" not in t.out
        assert "This is a debug" in t.out
        assert "This is a verbose" in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # Print also "trace" traces
        t.run("create . -vvv")
        assert "This is a trace" in t.out
        assert "This is a debug" in t.out
        assert "This is a verbose" in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out
        t.run("create . -vtrace")
        assert "This is a trace" in t.out
        assert "This is a debug" in t.out
        assert "This is a verbose" in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # With notice
        t.run("create . -vstatus")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" not in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # With notice
        t.run("create . -vnotice")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" not in t.out
        assert "This is a info" not in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # With warnings
        t.run("create . -vwarning")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" not in t.out
        assert "This is a info" not in t.out
        assert "This is a highlight" not in t.out
        assert "This is a success" not in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # With errors
        t.run("create . -verror")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" not in t.out
        assert "This is a info" not in t.out
        assert "This is a highlight" not in t.out
        assert "This is a success" not in t.out
        assert "This is a warning" not in t.out
        assert "This is a error" in t.out


def test_output_level_envvar():
    lines = ("self.output.trace('This is a trace')",
             "self.output.debug('This is a debug')",
             "self.output.verbose('This is a verbose')",
             "self.output.info('This is a info')",
             "self.output.highlight('This is a highlight')",
             "self.output.success('This is a success')",
             "self.output.warning('This is a warning')",
             "self.output.error('This is a error')",
             )

    t = TestClient(light=True)
    t.save({"conanfile.py": GenConanfile().with_package(*lines)})

    # Check if -v argument is equal to VERBOSE level
    with environment_update({"CONAN_LOG_LEVEL": "verbose"}):
        t.run("create . --name foo --version 1.0")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" in t.out
        assert "This is a info" in t.out
        assert "This is a highlight" in t.out
        assert "This is a success" in t.out
        assert "This is a warning" in t.out
        assert "This is a error" in t.out

        # Check if -v argument is equal to VERBOSE level
    with environment_update({"CONAN_LOG_LEVEL": "error"}):
        t.run("create . --name foo --version 1.0")
        assert "This is a trace" not in t.out
        assert "This is a debug" not in t.out
        assert "This is a verbose" not in t.out
        assert "This is a info" not in t.out
        assert "This is a highlight" not in t.out
        assert "This is a success" not in t.out
        assert "This is a warning" not in t.out
        assert "This is a error" in t.out


class TestWarningHandling:
    warning_lines = ("self.output.warning('Tagged warning', warn_tag='tag')",
                     "self.output.warning('Untagged warning')")
    error_lines = ("self.output.error('Tagged error', error_type='exception')",
                   "self.output.error('Untagged error')")

    def test_warning_as_error_deprecated_syntax(self):
        t = TestClient(light=True)
        t.save({"conanfile.py": GenConanfile("foo", "1.0").with_package(*self.warning_lines)})

        t.save_home({"global.conf": "core:warnings_as_errors=[]"})
        t.run("create . -vwarning")
        assert "WARN: Untagged warning" in t.out
        assert "WARN: tag: Tagged warning" in t.out

        t.save_home({"global.conf": "core:warnings_as_errors=['*']"})
        t.run("create . -vwarning", assert_error=True)
        assert "ConanException: tag: Tagged warning" in t.out
        # We bailed early, didn't get a chance to print this one
        assert "Untagged warning" not in t.out

        t.save_home({"global.conf": """core:warnings_as_errors=['*']\ncore:skip_warnings=["tag"]"""})
        t.run("create . -verror", assert_error=True)
        assert "ConanException: Untagged warning" in t.out
        assert "Tagged warning" not in t.out

        t.save_home({"global.conf": "core:warnings_as_errors=[]"})
        t.run("create . -verror")
        assert "ERROR: Untagged warning" not in t.out
        assert "ERROR: tag: Tagged warning" not in t.out

    def test_skip_warnings(self):
        t = TestClient(light=True)
        t.save({"conanfile.py": GenConanfile("foo", "1.0").with_package(*self.warning_lines)})

        t.save_home({"global.conf": "core:skip_warnings=[]"})
        t.run("create . -vwarning")
        assert "WARN: Untagged warning" in t.out
        assert "WARN: tag: Tagged warning" in t.out

        t.save_home({"global.conf": "core:skip_warnings=['tag']"})
        t.run("create . -vwarning")
        assert "WARN: Untagged warning" in t.out
        assert "WARN: tag: Tagged warning" not in t.out

        t.save_home({"global.conf": "core:skip_warnings=['unknown']"})
        t.run("create . -vwarning")
        assert "WARN: Untagged warning" not in t.out
        assert "WARN: tag: Tagged warning" in t.out

        t.save_home({"global.conf": "core:skip_warnings=['unknown', 'tag']"})
        t.run("create . -vwarning")
        assert "WARN: Untagged warning" not in t.out
        assert "WARN: tag: Tagged warning" not in t.out

    def test_exception_errors(self):
        t = TestClient(light=True)
        t.save({"conanfile.py": GenConanfile("foo", "1.0").with_package(*self.error_lines)})

        t.save_home({"global.conf": "core:warnings_as_errors=[]"})
        t.run("create .")
        assert "ERROR: Tagged error" in t.out
        assert "ERROR: Untagged error" in t.out

        t.save_home({"global.conf": "core:warnings_as_errors=['*']"})
        t.run("create .", assert_error=True)
        assert "ERROR: Tagged error" in t.out
        assert "ConanException: Untagged error" in t.out

        t.run("create . -vquiet", assert_error=True)
        assert "ERROR: Tagged error" not in t.out
        assert "ConanException: Untagged error" not in t.out


def test_formatter_redirection_to_file():
    c = TestClient(light=True)
    c.save({"conanfile.py":  GenConanfile("pkg", "0.1")})

    c.run("config home --out-file=cmd_out.txt")
    assert "Formatted output saved to 'cmd_out.txt'" in c.out
    cmd_out = c.load("cmd_out.txt")
    assert f"{c.cache_folder}" in cmd_out
    assert not f"{c.cache_folder}" in c.stdout

    c.run("graph info . --format=json --out-file=graph.json")
    assert "Formatted output saved to 'graph.json'" in c.out
    graph = json.loads(c.load("graph.json"))
    assert len(graph["graph"]["nodes"]) == 1
    assert "nodes" not in c.stdout

    c.run("graph info . --format=html --out-file=graph.html")
    assert "Formatted output saved to 'graph.html'" in c.out
    html = c.load("graph.html")
    assert "<head>" in html
    assert "<head>" not in c.stdout

    c.run("install . --format=json --out-file=graph.json")
    assert "Formatted output saved to 'graph.json'" in c.out
    graph = json.loads(c.load("graph.json"))
    assert len(graph["graph"]["nodes"]) == 1
    assert "nodes" not in c.stdout


def test_redirect_to_file_create_dir():
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("config home --out-file=subdir/cmd_out.txt")
    cmd_out = c.load("subdir/cmd_out.txt")
    assert f"{c.cache_folder}" in cmd_out

    base = temp_folder()
    c = TestClient(light=True, current_folder=os.path.join(base, "sub1"))
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("config home --out-file=../subdir/cmd_out.txt")
    cmd_out = c.load("../subdir/cmd_out.txt")
    assert f"{c.cache_folder}" in cmd_out


class TestOutputScope:

    @staticmethod
    def _conanfile(method, body):
        return textwrap.dedent(f"""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"

                def {method}(self):
                    {body}
            """)

    @pytest.mark.parametrize("method", ["source", "generate", "package"])
    def test_error_in_step_reports_the_reference(self, method):
        c = TestClient(light=True)
        c.save({"conanfile.py": self._conanfile(method, 'raise Exception("Boom!")')})
        c.run("create .", assert_error=True)
        assert f"ERROR: pkg/0.1: Error in {method}() method" in c.out

    @pytest.mark.parametrize("method", ["source", "generate", "package"])
    def test_invalid_configuration_in_step_reports_the_reference(self, method):
        c = TestClient(light=True)
        body = 'raise ConanInvalidConfiguration("Not valid!")'
        c.save({"conanfile.py": self._conanfile(method, body)})
        c.run("create .", assert_error=True)
        assert "ERROR: pkg/0.1: Invalid configuration: Not valid!" in c.out

    def test_hooks_keep_their_scope(self):
        hook = textwrap.dedent("""
            def pre_export(conanfile):
                conanfile.output.info("Msg from hook")

            def pre_generate(conanfile):
                conanfile.output.info("Msg from hook")
            """)
        c = TestClient(light=True)
        save(os.path.join(c.paths.hooks_path, "hook_scope.py"), hook)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("create .")
        # ``export`` is not inside a step block, the hook scope is appended to the reference
        assert "pkg/0.1: [HOOK - hook_scope.py] pre_export(): Msg from hook" in c.out
        # the generate step is, so only the hook scope is left
        assert "[HOOK - hook_scope.py] pre_generate(): Msg from hook" in c.out
        assert "pkg/0.1: [HOOK - hook_scope.py] pre_generate()" not in c.out
