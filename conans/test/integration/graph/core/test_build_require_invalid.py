import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


class TestInvalidConfiguration:
    """
    ConanInvalidConfiguration without a binary fall backs, result in errors
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            settings = "os"

            def validate(self):
                if self.settings.os == "Windows":
                    raise ConanInvalidConfiguration("Package does not work in Windows!")
       """)
    linux_package_id = "02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8"
    invalid = "Invalid"

    @pytest.fixture(scope="class")
    def client(self):
        client = TestClient()
        client.save({"pkg/conanfile.py": self.conanfile})
        client.run("create pkg --name=pkg --version=0.1 -s os=Linux")
        return client

    def test_invalid(self, client):
        conanfile_consumer = GenConanfile().with_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Windows", assert_error=True)
        assert "pkg/0.1: {}: Package does not work in Windows!".format(self.invalid) in client.out

    def test_invalid_info(self, client):
        """
        the conan info command does not raise, but it outputs info
        """
        conanfile_consumer = GenConanfile().with_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("graph info consumer -s os=Windows")
        assert "binary: {}".format(self.invalid) in client.out

    def test_valid(self, client):
        conanfile_consumer = GenConanfile().with_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Linux")
        client.assert_listed_binary({"pkg/0.1": (self.linux_package_id, "Cache")})
        assert "pkg/0.1: Already installed!" in client.out

    def test_invalid_build_require(self, client):
        conanfile_consumer = GenConanfile().with_tool_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s:h os=Windows -s:b os=Windows", assert_error=True)
        assert "pkg/0.1: {}: Package does not work in Windows!".format(self.invalid) in client.out

    def test_valid_build_require_two_profiles(self, client):
        conanfile_consumer = GenConanfile().with_tool_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s:b os=Linux -s:h os=Windows")
        client.assert_listed_binary({"pkg/0.1": (self.linux_package_id, "Cache")}, build=True)
        assert "pkg/0.1: Already installed!" in client.out


class TestErrorConfiguration(TestInvalidConfiguration):
    """
    A configuration error is unsolvable, even if a binary exists
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conans.errors import ConanErrorConfiguration

        class Conan(ConanFile):
            settings = "os"

            def validate(self):
                if self.settings.os == "Windows":
                    raise ConanErrorConfiguration("Package does not work in Windows!")

            def package_id(self):
                del self.info.settings.os
        """)
    linux_package_id = NO_SETTINGS_PACKAGE_ID
    invalid = "ConfigurationError"


class TestErrorConfigurationCompatible(TestInvalidConfiguration):
    """
    A configuration error is unsolvable, even if a binary exists
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conans.errors import ConanErrorConfiguration

        class Conan(ConanFile):
            settings = "os"

            def validate(self):
                if self.settings.os == "Windows":
                    raise ConanErrorConfiguration("Package does not work in Windows!")

            def package_id(self):
               if self.settings.os == "Windows":
                   compatible_pkg = self.info.clone()
                   compatible_pkg.settings.os = "Linux"
                   self.compatible_packages.append(compatible_pkg)
        """)
    linux_package_id = "02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8"
    invalid = "ConfigurationError"


class TestInvalidBuildPackageID:
    """
    ConanInvalidBuildConfiguration will not block if setting is removed from package_id
    """
    conanfile = textwrap.dedent("""
       from conan import ConanFile
       from conans.errors import ConanInvalidConfiguration

       class Conan(ConanFile):
           settings = "os"

           def validate(self):
               if self.settings.os == "Windows":
                   raise ConanInvalidConfiguration("Package does not work in Windows!")

           def package_id(self):
               del self.info.settings.os
       """)
    linux_package_id = NO_SETTINGS_PACKAGE_ID

    @pytest.fixture(scope="class")
    def client(self):
        client = TestClient()
        client.save({"pkg/conanfile.py": self.conanfile})
        client.run("create pkg --name=pkg --version=0.1 -s os=Linux")
        return client

    def test_valid(self, client):
        conanfile_consumer = GenConanfile().with_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Windows")
        client.assert_listed_binary({"pkg/0.1": (self.linux_package_id, "Cache")})
        assert "pkg/0.1: Already installed!" in client.out

        client.run("install consumer -s os=Linux")
        client.assert_listed_binary({"pkg/0.1": (self.linux_package_id, "Cache")})
        assert "pkg/0.1: Already installed!" in client.out

    def test_invalid_try_build(self, client):
        conanfile_consumer = GenConanfile().with_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Windows --build", assert_error=True)
        # Only when trying to build, it will try to build the Windows one
        client.assert_listed_binary({"pkg/0.1": ("INVALID", "Invalid")})
        assert "pkg/0.1: Invalid: Package does not work in Windows!" in client.out

    def test_valid_build_require_two_profiles(self, client):
        conanfile_consumer = GenConanfile().with_tool_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s:b os=Linux -s:h os=Windows")
        client.assert_listed_binary({"pkg/0.1": (self.linux_package_id, "Cache")}, build=True)
        assert "pkg/0.1: Already installed!" in client.out

        client.run("install consumer -s:b os=Windows -s:h os=Windows")
        client.assert_listed_binary({"pkg/0.1": (self.linux_package_id, "Cache")}, build=True)
        assert "pkg/0.1: Already installed!" in client.out


class TestInvalidBuildCompatible(TestInvalidBuildPackageID):
    """
    ConanInvalidBuildConfiguration will not block if compatible_packages fallback
    """
    conanfile = textwrap.dedent("""
       from conan import ConanFile
       from conans.errors import ConanInvalidConfiguration

       class Conan(ConanFile):
           settings = "os"

           def validate(self):
               if self.settings.os == "Windows":
                   raise ConanInvalidConfiguration("Package does not work in Windows!")

           def package_id(self):
               if self.settings.os == "Windows":
                   compatible_pkg = self.info.clone()
                   compatible_pkg.settings.os = "Linux"
                   self.compatible_packages.append(compatible_pkg)
       """)
    linux_package_id = "02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8"
