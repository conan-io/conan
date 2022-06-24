from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


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

    # With warnings only warnings
    t.run("create . --name foo --version 1.0 -ow")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" not in t.out
    assert "This is a info" not in t.out
    assert "This is a highlight" not in t.out
    assert "This is a success" not in t.out
    assert "This is a warning" in t.out
    assert "This is a error" in t.out

    # With errors only errors
    t.run("create . --name foo --version 1.0 -oe")
    assert "This is a trace" not in t.out
    assert "This is a debug" not in t.out
    assert "This is a verbose" not in t.out
    assert "This is a info" not in t.out
    assert "This is a highlight" not in t.out
    assert "This is a success" not in t.out
    assert "This is a warning" not in t.out
    assert "This is a error" in t.out

