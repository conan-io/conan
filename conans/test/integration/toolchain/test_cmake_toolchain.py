import platform

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.parametrize("compiler, version, runtime",
                         [("msvc", "19.2", "dynamic"),
                          ("msvc", "19.26", "static"),
                          ("msvc", "19.28", "static")])
def test_cmake_toolchain_win_toolset(compiler, version, runtime):
    client = TestClient(path_with_spaces=False)
    settings = {"compiler": compiler,
                "compiler.version": version,
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
    if len(version) == 5:  # Fullversion
        minor = version.split(".")[1]
        value = "version=14.{}".format(minor)
    else:
        value = "v142"
    assert 'set(CMAKE_GENERATOR_TOOLSET "{}" CACHE STRING "" FORCE)'.format(value) in toolchain

