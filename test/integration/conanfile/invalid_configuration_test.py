import textwrap

import pytest

from conan.cli.exit_codes import ERROR_INVALID_CONFIGURATION
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestInvalidConfiguration:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = TestClient()
        conanfile = textwrap.dedent("""\

            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration

            class MyPkg(ConanFile):
                settings = "os", "compiler", "build_type", "arch"

                def configure(self):
                    if self.settings.compiler.version == "190":
                        raise ConanInvalidConfiguration("compiler.version=12 is invalid!!")
            """)
        self.client.save({"conanfile.py": conanfile})
        settings = "-s os=Windows -s compiler=msvc -s compiler.version={ver} "\
                   "-s compiler.runtime=dynamic"
        self.settings_msvc15 = settings.format(ver="192")
        self.settings_msvc12 = settings.format(ver="190")

    def test_install_method(self):
        self.client.run("install . %s" % self.settings_msvc15)

        error = self.client.run("install . %s" % self.settings_msvc12, assert_error=True)
        assert error == ERROR_INVALID_CONFIGURATION
        assert "Invalid configuration: compiler.version=12 is invalid!!" in self.client.out

    def test_info_method(self):
        self.client.run("graph info . %s" % self.settings_msvc15)

        error = self.client.run("graph info . %s" % self.settings_msvc12, assert_error=True)
        assert error == ERROR_INVALID_CONFIGURATION
        assert "Invalid configuration: compiler.version=12 is invalid!!" in self.client.out

    def test_create_method(self):
        self.client.run("create . --name=name --version=ver %s" % self.settings_msvc15)

        error = self.client.run("create . --name=name --version=ver %s" % self.settings_msvc12,
                                assert_error=True)
        assert error == ERROR_INVALID_CONFIGURATION
        assert "name/ver: Invalid configuration: compiler.version=12 is invalid!!" in self.client.out

    def test_as_requirement(self):
        self.client.run("create . --name=name --version=ver %s" % self.settings_msvc15)
        self.client.save({"other/conanfile.py": GenConanfile().with_requirement("name/ver")})
        self.client.run("create other/ --name=other --version=1.0 %s" % self.settings_msvc15)

        error = self.client.run("create other/ --name=other --version=1.0 %s" % self.settings_msvc12,
                                assert_error=True)
        assert error == ERROR_INVALID_CONFIGURATION
        assert "name/ver: Invalid configuration: compiler.version=12 is invalid!!" in self.client.out
