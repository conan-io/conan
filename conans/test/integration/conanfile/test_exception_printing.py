from parameterized import parameterized

from conans.client import tools
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient


conanfile = """
from conans import ConanFile

class DRLException(Exception):
    pass

class ExceptionsTest(ConanFile):
    name = "exceptions"
    version = "0.1"

    def {method}(self):
        {method_contents}

    def _aux_method(self):
        raise DRLException('Oh! an error!')
"""


@parameterized.expand([(True,), (False,)])
def test_all_methods(direct):
    client = TestClient()
    if direct:
        throw = "raise DRLException('Oh! an error!')"
    else:
        throw = "self._aux_method()"
    for method in ["source", "build", "package", "package_info", "configure", "build_id",
                   "package_id", "requirements", "config_options", "layout", "generate", "export",
                   "export_sources"]:
        client.save({CONANFILE: conanfile.format(method=method, method_contents=throw)})
        client.run("create . ", assert_error=True)
        assert "exceptions/0.1: Error in %s() method, line 12" % method in client.out
        assert "DRLException: Oh! an error!" in client.out
        if not direct:
            assert "while calling '_aux_method', line 15" in client.out


def test_complete_traceback():
    client = TestClient()
    throw = "self._aux_method()"
    client.save({CONANFILE: conanfile.format(method="source", method_contents=throw)})
    with tools.environment_append({"CONAN_VERBOSE_TRACEBACK": "1"}):
        client.run("create . ", assert_error=True)
        assert "DRLException: Oh! an error!" in client.out
        assert "ERROR: Traceback (most recent call last):" in client.out
