import platform


import pytest
from parameterized import parameterized

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@parameterized.expand([("msvc", "19.2", "dynamic"),
                       ("msvc", "19.26", "static"),
                       ("msvc", "19.28", "static")]
                      )
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_toolchain_win(compiler, version, runtime):
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
        line = 'set(CMAKE_GENERATOR_TOOLSET "version=14.{}" CACHE STRING "" FORCE)'
        minor = version.split(".")[1]
        assert line.format(minor) in toolchain
    else:
        assert "CMAKE_GENERATOR_TOOLSET" not in toolchain
