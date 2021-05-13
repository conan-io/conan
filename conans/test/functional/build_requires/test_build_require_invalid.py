import os
import textwrap

import pytest
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def setup_client_with_build_requires():
    client = TestClient()
    conanfile_validate = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            name = "br"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"

            def validate(self):
                if self.settings.build_type == "Debug":
                    raise ConanInvalidConfiguration("br cannot be built in debug mode")
        """)
    conanfile_configure = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            name = "br"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"

            def configure(self):
                if self.settings.build_type == "Debug":
                    raise ConanInvalidConfiguration("br cannot be built in debug mode")
        """)
    conanfile_build = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            name = "br"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"

            def build(self):
                if self.settings.build_type == "Debug":
                    raise ConanInvalidConfiguration("br cannot be built in debug mode")
        """)
    conanfile_validate_pacakge_id = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            name = "br"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"

            def validate(self):
                if self.settings.build_type == "Debug":
                    raise ConanInvalidConfiguration("br cannot be built in debug mode")

            def package_id(self):
                del self.info.settings.build_type
        """)
    conanfile_configure_pacakge_id = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            name = "br"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"

            def configure(self):
                if self.settings.build_type == "Debug":
                    raise ConanInvalidConfiguration("br cannot be built in debug mode")

            def package_id(self):
                del self.info.settings.build_type
        """)
    conanfile_build_package_id = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conans.errors import ConanInvalidConfiguration

        class Conan(ConanFile):
            name = "br"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"

            def build(self):
                if self.settings.build_type == "Debug":
                    raise ConanInvalidConfiguration("br cannot be built in debug mode")

            def package_id(self):
                del self.info.settings.build_type
        """)
    conanfile_validate_compatible = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration

            class Conan(ConanFile):
                name = "br"
                version = "1.0.0"
                settings = "os", "compiler", "build_type", "arch"

                def validate(self):
                    if self.settings.build_type == "Debug":
                        raise ConanInvalidConfiguration("br cannot be built in debug mode")

                def package_id(self):
                    if self.settings.build_type == "Debug":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.build_type = "Release"
                        self.compatible_packages.append(compatible_pkg)
            """)
    conanfile_configure_compatible = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration

            class Conan(ConanFile):
                name = "br"
                version = "1.0.0"
                settings = "os", "compiler", "build_type", "arch"

                def configure(self):
                    if self.settings.build_type == "Debug":
                        raise ConanInvalidConfiguration("br cannot be built in debug mode")

                def package_id(self):
                    if self.settings.build_type == "Debug":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.build_type = "Release"
                        self.compatible_packages.append(compatible_pkg)
            """)
    conanfile_build_compatible = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration

            class Conan(ConanFile):
                name = "br"
                version = "1.0.0"
                settings = "os", "compiler", "build_type", "arch"

                def build(self):
                    if self.settings.build_type == "Debug":
                        raise ConanInvalidConfiguration("br cannot be built in debug mode")

                def package_id(self):
                    if self.settings.build_type == "Debug":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.build_type = "Release"
                        self.compatible_packages.append(compatible_pkg)
            """)
    conanfile_consumer = textwrap.dedent("""
        from conans import ConanFile, CMake

        class Conan(ConanFile):
            name = "libA"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"
            build_requires = "br/1.0.0"
        """)
    client.save({"br_validate.py": conanfile_validate,
                 "br_configure.py": conanfile_configure,
                 "br_build.py": conanfile_build,
                 "br_validate_pid.py": conanfile_validate_pacakge_id,
                 "br_configure_pid.py": conanfile_configure_pacakge_id,
                 "br_build_pid.py": conanfile_build_package_id,
                 "br_validate_compatible.py": conanfile_validate_compatible,
                 "br_configure_compatible.py": conanfile_configure_compatible,
                 "br_build_compatible.py": conanfile_build_compatible,
                 "consumer.py": conanfile_consumer})
    return client


def test_create_invalid_validate(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_configure(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_build(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_validate_pid(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_pid.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_configure_pid(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure_pid.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_build_pid(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build_pid.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_validate_compatible(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_compatible.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_configure_compatible(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure_compatible.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_build_compatible(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build_compatible.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_validate_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate.py")
    client.run("create consumer.py -s build_type=Debug -pr:b=default -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_configure_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure.py")
    client.run("create consumer.py -s build_type=Debug -pr:b=default -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_build_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build.py")
    client.run("create consumer.py -s build_type=Debug -pr:b=default -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_validate_pid_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_pid.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_configure_pid_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure_pid.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_build_pid_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build_pid.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_validate_compatible_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_compatible.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_configure_compatible_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure_compatible.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_build_compatible_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build_compatible.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
    assert "br/1.0.0 from local cache - Cache" in client.out
