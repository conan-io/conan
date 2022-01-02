import pytest

from conan.tools._check_build_profile import check_msg
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("tool_class", ["CMakeDeps", "CMakeToolchain", "AutotoolsToolchain",
                                        "AutotoolsDeps", "MSBuildToolchain", "MSBuildDeps",
                                        "BazelDeps", "BazelToolchain", "MesonToolchain"])
def test_warning_message(tool_class):
    """FIXME: Remove in Conan 2.0"""
    client = TestClient()
    r = str(GenConanfile().with_name("lib").with_version("1.0")
            .with_settings("os", "arch", "build_type", "compiler")
            .with_import("from conan.tools.cmake import CMakeDeps, CMakeToolchain")
            .with_import("from conan.tools.gnu import AutotoolsDeps, AutotoolsToolchain")
            .with_import("from conan.tools.microsoft import MSBuildDeps, MSBuildToolchain")
            .with_import("from conan.tools.google import BazelDeps, BazelToolchain")
            .with_import("from conan.tools.meson import MesonToolchain"))

    r += """
    def generate(self):
        {}(self)
    """.format(tool_class)

    client.save({"conanfile.py": r})

    client.run("create . ")
    assert check_msg in client.out

    client.run("create . -pr:b=default")
    assert check_msg not in client.out


@pytest.mark.parametrize("cmake_deps_property", ["build_context_activated",
                                                 "build_context_build_modules",
                                                 "build_context_suffix",
                                                 False])
def test_error_cmake_deps_without_build_profile(cmake_deps_property):
    client = TestClient()
    r = str(GenConanfile().with_name("lib").with_version("1.0")
            .with_settings("os", "arch", "build_type", "compiler")
            .with_import("from conan.tools.cmake import CMakeDeps"))

    r += """
    def generate(self):
        deps = CMakeDeps(self)
        {}
        deps.generate()
    """.format("deps.{} = ['foo']".format(cmake_deps_property) if cmake_deps_property else "")

    client.save({"conanfile.py": r})

    client.run("create . ", assert_error=cmake_deps_property)
    if cmake_deps_property:
        assert "The 'build_context_activated' and 'build_context_build_modules' of the CMakeDeps " \
               "generator cannot be used without specifying a build profile. e.g: -pr:b=default"\
               in client.out

    client.run("create . -pr:b=default")
    assert "The 'build_context_activated' and 'build_context_build_modules' of the CMakeDeps " \
           "generator cannot be used without specifying a build profile. e.g: -pr:b=default" \
           not in client.out
