import textwrap

import pytest
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def setup_client_with_build_requires():
    client = TestClient()
    conanfile_validate = textwrap.dedent("""
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
                del self.info.settings.compiler
        """)
    conanfile_configure = textwrap.dedent("""
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
                del self.info.settings.compiler
        """)
    conanfile_build = textwrap.dedent("""
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
                del self.info.settings.compiler
        """)
    conanfile_validate_remove_build_type = textwrap.dedent("""
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
                del self.info.settings.compiler
                del self.info.settings.build_type
        """)
    conanfile_configure_remove_build_type = textwrap.dedent("""
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
                del self.info.settings.compiler
                del self.info.settings.build_type
        """)
    conanfile_build_remove_build_type = textwrap.dedent("""
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
                del self.info.settings.compiler
                del self.info.settings.build_type
        """)
    conanfile_validate_compatible = textwrap.dedent("""
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
                    del self.info.settings.compiler
                    if self.settings.build_type == "Debug":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.build_type = "Release"
                        self.compatible_packages.append(compatible_pkg)
            """)
    conanfile_validate_compatible_unbuildable = textwrap.dedent("""
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
                del self.info.settings.compiler
                if self.settings.build_type == "Debug":
                    compatible_pkg = self.info.clone()
                    compatible_pkg.settings.build_type = "Release"
                    self.compatible_packages.append(compatible_pkg)
        """)
    conanfile_configure_compatible = textwrap.dedent("""
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
                    del self.info.settings.compiler
                    if self.settings.build_type == "Debug":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.build_type = "Release"
                        self.compatible_packages.append(compatible_pkg)
            """)
    conanfile_build_compatible = textwrap.dedent("""
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
                    del self.info.settings.compiler
                    if self.settings.build_type == "Debug":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.build_type = "Release"
                        self.compatible_packages.append(compatible_pkg)
            """)
    conanfile_consumer = textwrap.dedent("""
        from conans import ConanFile

        class Conan(ConanFile):
            name = "libA"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"
            build_requires = "br/1.0.0"
        """)
    client.save({"br_validate.py": conanfile_validate,
                 "br_configure.py": conanfile_configure,
                 "br_build.py": conanfile_build,
                 "br_validate_remove_build_type.py": conanfile_validate_remove_build_type,
                 "br_configure_remove_build_type.py": conanfile_configure_remove_build_type,
                 "br_build_remove_build_type.py": conanfile_build_remove_build_type,
                 "br_validate_compatible.py": conanfile_validate_compatible,
                 "br_validate_compatible_unbuildable.py": conanfile_validate_compatible_unbuildable,
                 "br_configure_compatible.py": conanfile_configure_compatible,
                 "br_build_compatible.py": conanfile_build_compatible,
                 "consumer.py": conanfile_consumer})
    return client


def test_create_invalid_validate(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate.py")  # In Release mode, it works
    client.run("create consumer.py -s build_type=Debug", assert_error=True)
    # Expected, we are telling the br to use Debug mode
    print(client.out)
    assert "br/1.0.0: Invalid ID: br cannot be built in debug mode" in client.out


def test_create_invalid_configure(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure.py")
    client.run("create consumer.py -s build_type=Debug", assert_error=True)
    # Expected, we are telling the br to use Debug mode
    assert "ERROR: br/1.0.0: Invalid configuration: br cannot be built in debug mode" in client.out


def test_create_invalid_build(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build.py")
    client.run("create consumer.py -s build_type=Debug", assert_error=True)
    assert "ERROR: Missing binary: br/1.0.0" in client.out
    client.run("create consumer.py -s build_type=Debug --build", assert_error=True)
    assert "ERROR: br/1.0.0: Invalid configuration: br cannot be built in debug mode" in client.out


def test_create_validate_remove_build_type(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_remove_build_type.py")
    # FIXME: This should NOT fail with -> br/1.0.0: Invalid ID: br cannot be built in debug mode
    client.run("create consumer.py -s build_type=Debug")


def test_create_configure_remove_build_type(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure_remove_build_type.py")
    # FIXME: This should NOT fail with -> ERROR: br/1.0.0: Invalid configuration: br cannot be built in debug mode
    client.run("create consumer.py -s build_type=Debug", assert_error=True)


def test_create_build_remove_build_type(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build_remove_build_type.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_validate_compatible(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_compatible.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "Using compatible package" in client.out


def test_create_validate_compatible_unbuildable(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_compatible_unbuildable.py")
    client.run("create consumer.py -s build_type=Debug")
    print(client.out)
    assert "Using compatible package" in client.out


def test_create_configure_compatible(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure_compatible.py")
    # FIXME: This should NOT fail with -> ERROR: br/1.0.0: Invalid configuration: br cannot be built in debug mode
    client.run("create consumer.py -s build_type=Debug", assert_error=True)


def test_create_build_compatible(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build_compatible.py")
    client.run("create consumer.py -s build_type=Debug")
    assert "Using compatible package" in client.out


def test_create_validate_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate.py")
    client.run("create consumer.py -pr:b=default -s:h build_type=Debug -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_configure_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure.py")
    client.run("create consumer.py -pr:b=default -s:h build_type=Debug -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_build_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build.py")
    client.run("create consumer.py -pr:b=default -s:h build_type=Debug -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_validate_remove_build_type_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_remove_build_type.py")
    # FIXME: This should NOT fail with -> br/1.0.0: Invalid ID: br cannot be built in debug mode
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")


def test_create_configure_remove_build_type_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure_remove_build_type.py")
    # FIXME: This should NOT fail with -> ERROR: br/1.0.0: Invalid configuration: br cannot be built in debug mode
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default", assert_error=True)


def test_create_build_remove_build_type_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build_remove_build_type.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_validate_compatible_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate_compatible.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
    assert "Using compatible package" in client.out


def test_create_configure_compatible_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure_compatible.py")
    # FIXME: This should NOT fail with -> br/1.0.0: Invalid ID: br cannot be built in debug mode
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default", assert_error=True)


def test_create_build_compatible_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build_compatible.py")
    client.run("create consumer.py -s:b build_type=Debug -pr:b default "
               "-s:h build_type=Debug -pr:h default")
