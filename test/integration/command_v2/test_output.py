from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.test.utils.env import environment_update


class TestOutputLevel:
    def test_invalid_output_level(self):
        t = TestClient(light=True)
        t.save({"conanfile.py": GenConanfile("foo", "1.0")})
        t.run("create . -vfooling", assert_error=True)
        assert "Invalid argument '-vfooling'"

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
