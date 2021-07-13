import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


class TestInvalidConfiguration:
    """
    ConanInvalidConfiguration blocks any usage or build
    """
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            settings = "os"

            def validate(self):
                if self.settings.os == "Windows":
                    raise ConanInvalidConfiguration("Package does not work in Windows!")
       """)
    package_id = "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"
    invalid = "Invalid"

    @pytest.fixture(scope="class")
    def client(self):
        client = TestClient()
        client.save({"pkg/conanfile.py": self.conanfile})
        client.run("create pkg pkg/0.1@ -s os=Linux")
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
        client.run("info consumer -s os=Windows")
        assert "Binary: {}".format(self.invalid) in client.out

    def test_valid(self, client):
        conanfile_consumer = GenConanfile().with_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Linux")
        assert "pkg/0.1:{} - Cache".format(self.package_id) in client.out
        assert "pkg/0.1: Already installed!" in client.out

    def test_invalid_build_require(self, client):
        conanfile_consumer = GenConanfile().with_build_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Windows", assert_error=True)
        assert "pkg/0.1: {}: Package does not work in Windows!".format(self.invalid) in client.out

    def test_valid_build_require_two_profiles(self, client):
        conanfile_consumer = GenConanfile().with_build_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s:b os=Linux -s:h os=Windows")
        assert "pkg/0.1:{} - Cache".format(self.package_id) in client.out
        assert "pkg/0.1: Already installed!" in client.out


class TestInvalidConfigurationRemovePackageId(TestInvalidConfiguration):
    """
    ConanInvalidConfiguration blocks even if package-id removes setting, test to verify
    the behavior of ConanInvalidConfiguration is the same
    """
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            settings = "os"

            def validate(self):
                if self.settings.os == "Windows":
                    raise ConanInvalidConfiguration("Package does not work in Windows!")

            def package_id(self):
                del self.info.settings.os
        """)
    package_id = NO_SETTINGS_PACKAGE_ID


class TestInvalidBuildConfiguration(TestInvalidConfiguration):
    """
    ConanInvalidBuildConfiguration still blocks if not removing settings
    This configuration does NOT really make sense without removing in package_id
    or using compatible_packages
    """
    conanfile = textwrap.dedent("""
       from conans import ConanFile
       from conans.errors import ConanInvalidBuildConfiguration

       class Conan(ConanFile):
           settings = "os"

           def validate(self):
               if self.settings.os == "Windows":
                   raise ConanInvalidBuildConfiguration("Package does not work in Windows!")
       """)
    invalid = "InvalidBuild"


class TestInvalidBuildPackageID:
    """
    ConanInvalidBuildConfiguration will not block if setting is removed from package_id
    """
    conanfile = textwrap.dedent("""
       from conans import ConanFile
       from conans.errors import ConanInvalidBuildConfiguration

       class Conan(ConanFile):
           settings = "os"

           def validate(self):
               if self.settings.os == "Windows":
                   raise ConanInvalidBuildConfiguration("Package does not work in Windows!")

           def package_id(self):
               del self.info.settings.os
       """)
    package_id = NO_SETTINGS_PACKAGE_ID
    windows_package_id = NO_SETTINGS_PACKAGE_ID

    @pytest.fixture(scope="class")
    def client(self):
        client = TestClient()

        client.save({"pkg/conanfile.py": self.conanfile})
        client.run("create pkg pkg/0.1@ -s os=Linux")
        return client

    def test_valid(self, client):
        conanfile_consumer = GenConanfile().with_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Windows")
        assert "pkg/0.1:{} - Cache".format(self.package_id) in client.out
        assert "pkg/0.1: Already installed!" in client.out

        client.run("install consumer -s os=Linux")
        assert "pkg/0.1:{} - Cache".format(self.package_id) in client.out
        assert "pkg/0.1: Already installed!" in client.out

    def test_invalid_try_build(self, client):
        conanfile_consumer = GenConanfile().with_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Windows --build", assert_error=True)
        # Only when trying to build, it will try to build the Windows one
        assert "pkg/0.1:{} - InvalidBuild".format(self.windows_package_id) in client.out
        assert "pkg/0.1: InvalidBuild: Package does not work in Windows!" in client.out

    def test_valid_build_require(self, client):
        conanfile_consumer = GenConanfile().with_build_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s os=Windows")
        assert "pkg/0.1:{} - Cache".format(self.package_id) in client.out
        assert "pkg/0.1: Already installed!" in client.out

        client.run("install consumer -s os=Linux")
        assert "pkg/0.1:{} - Cache".format(self.package_id) in client.out
        assert "pkg/0.1: Already installed!" in client.out

    def test_valid_build_require_two_profiles(self, client):
        conanfile_consumer = GenConanfile().with_build_requires("pkg/0.1").with_settings("os")
        client.save({"consumer/conanfile.py": conanfile_consumer})
        client.run("install consumer -s:b os=Linux -s:h os=Windows")
        assert "pkg/0.1:{} - Cache".format(self.package_id) in client.out
        assert "pkg/0.1: Already installed!" in client.out

        client.run("install consumer -s:b os=Windows -s:h os=Windows")
        assert "pkg/0.1:{} - Cache".format(self.package_id) in client.out
        assert "pkg/0.1: Already installed!" in client.out


class TestInvalidBuildCompatible(TestInvalidBuildPackageID):
    """
    ConanInvalidBuildConfiguration will not block if compatible_packages fallback
    """
    conanfile = textwrap.dedent("""
       from conans import ConanFile
       from conans.errors import ConanInvalidBuildConfiguration

       class Conan(ConanFile):
           settings = "os"

           def validate(self):
               if self.settings.os == "Windows":
                   raise ConanInvalidBuildConfiguration("Package does not work in Windows!")

           def package_id(self):
               if self.settings.os == "Windows":
                   compatible_pkg = self.info.clone()
                   compatible_pkg.settings.os = "Linux"
                   self.compatible_packages.append(compatible_pkg)
       """)
    package_id = "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"
    windows_package_id = "3475bd55b91ae904ac96fde0f106a136ab951a5e"
