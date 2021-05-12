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
    conanfile_consumer = textwrap.dedent("""
        from conans import ConanFile, CMake

        class Conan(ConanFile):
            name = "libA"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"
            build_requires = "br/1.0.0"
        """)
    client.save({"br_validate.py": conanfile_validate, "br_configure.py": conanfile_configure,
                 "br_build.py": conanfile_build, "consumer.py": conanfile_consumer})
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


def test_create_invalid_validate_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_validate.py")
    client.run("create consumer.py -s build_type=Debug -pr:b=default -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_configure_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_configure.py")
    client.run("create consumer.py -s build_type=Debug -pr:b=default -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out


def test_create_invalid_build_two_profiles(setup_client_with_build_requires):
    client = setup_client_with_build_requires
    client.run("create br_build.py")
    client.run("create consumer.py -s build_type=Debug -pr:b=default -pr:h=default")
    assert "br/1.0.0 from local cache - Cache" in client.out
