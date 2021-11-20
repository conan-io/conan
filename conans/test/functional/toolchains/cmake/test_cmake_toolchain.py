import os
import platform
import textwrap

import pytest

from conan.tools.files import load_toolchain_args
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.parametrize("compiler, version, update, runtime",
                         [("msvc", "192", None, "dynamic"),
                          ("msvc", "192", "6", "static"),
                          ("msvc", "192", "8", "static")])
def test_cmake_toolchain_win_toolset(compiler, version, update, runtime):
    client = TestClient(path_with_spaces=False)
    settings = {"compiler": compiler,
                "compiler.version": version,
                "compiler.update": update,
                "compiler.cppstd": "17",
                "compiler.runtime": runtime,
                "build_type": "Release",
                "arch": "x86_64"}

    # Build the profile according to the settings provided
    settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")

    client.save({"conanfile.py": conanfile})
    client.run("install . {}".format(settings))
    toolchain = client.load("conan_toolchain.cmake")
    if update is not None:  # Fullversion
        value = "version=14.{}{}".format(version[-1], update)
    else:
        value = "v14{}".format(version[-1])
    assert 'set(CMAKE_GENERATOR_TOOLSET "{}" CACHE STRING "" FORCE)'.format(value) in toolchain


def test_cmake_toolchain_user_toolchain():
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")
    save(client.cache.new_config_path, "tools.cmake.cmaketoolchain:user_toolchain=mytoolchain.cmake")

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'include("mytoolchain.cmake")' in toolchain


def test_cmake_toolchain_custom_toolchain():
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")
    save(client.cache.new_config_path, "tools.cmake.cmaketoolchain:toolchain_file=mytoolchain.cmake")

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    assert not os.path.exists(os.path.join(client.current_folder, "conan_toolchain.cmake"))
    build_content = load_toolchain_args(client.current_folder)
    assert "mytoolchain.cmake" == build_content["cmake_toolchain_file"]


def test_cmake_toolchain_user_toolchain_from_dep():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        class Pkg(ConanFile):
            exports_sources = "*"
            def package(self):
                self.copy("*")
            def package_info(self):
                f = os.path.join(self.package_folder, "mytoolchain.cmake")
                self.conf_info["tools.cmake.cmaketoolchain:user_toolchain"] = f
        """)
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain.cmake !!!running!!!")'})
    client.run("create . toolchain/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            build_requires = "toolchain/0.1"
            generators = "CMakeToolchain"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": gen_cmakelists()}, clean_first=True)
    client.run("create . pkg/0.1@")
    assert "mytoolchain.cmake !!!running!!!" in client.out
