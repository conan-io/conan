import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

conanfile = """
from conan import ConanFile

class ExceptionsTest(ConanFile):
    name = "exceptions"
    version = "0.1"

    def {method}(self):
        {method_contents}

    def _aux_method(self):
        raise Exception('Oh! an error!')
"""


@pytest.mark.parametrize("direct", [True, False])
@pytest.mark.parametrize("method",
                         ["source", "build", "package", "package_info", "configure", "build_id",
                          "package_id", "requirements", "config_options", "layout", "generate",
                          "export", "export_sources", "build_requirements", "init"])
def test_all_methods(direct, method):
    client = TestClient()
    if direct:
        throw = "raise Exception('Oh! an error!')"
    else:
        throw = "self._aux_method()"

    client.save({"conanfile.py": conanfile.format(method=method, method_contents=throw)})
    client.run("create . ", assert_error=True)
    assert "Error in %s() method, line 9" % method in client.out
    assert "Oh! an error!" in client.out
    if not direct:
        assert "while calling '_aux_method', line 12" in client.out


def test_complete_traceback_debug():
    """
    in debug level (-vv), the trace is shown (this is for recipe methods exceptions)
    """
    client = TestClient()
    throw = "self._aux_method()"
    client.save({"conanfile.py": conanfile.format(method="source", method_contents=throw)})
    client.run("create . -vv", assert_error=True)
    assert "Exception: Oh! an error!" in client.out
    assert "ERROR: Traceback (most recent call last):" in client.out


def test_complete_traceback_trace():
    """
    in debug level (-vvv), the full trace is shown for ConanExceptions
    """
    client = TestClient()
    client.run("install --requires=pkg/1.0 -vvv", assert_error=True)
    assert "Traceback (most recent call last)" in client.out


def test_notracebacks_cmakedeps():
    """
    CMakeDeps prints traceback
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_generator("CMakeDeps")})
    c.run("install .", assert_error=True)
    assert "Traceback" not in c.out
    assert "ERROR: Error in generator 'CMakeDeps'" in c.out
