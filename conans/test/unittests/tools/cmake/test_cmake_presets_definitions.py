import pytest
from mock import mock
from mock.mock import Mock

from conan.tools.cmake import CMake
from conan.tools.cmake.presets import write_cmake_presets
from conan.tools.files.files import save_toolchain_args
from conans import ConanFile, Settings
from conans.model.conf import Conf
from conans.model.env_info import EnvValues
from conans.test.utils.test_files import temp_folder


@pytest.fixture(scope="module")
def conanfile():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.initialize(Settings({"os": ["Windows"],
                           "compiler": {"gcc": {"libcxx": ["libstdc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "gcc"
    c.settings.compiler.libcxx = "libstdc++"
    c.settings.os = "Windows"
    c.conf = Conf()
    tmp_folder = temp_folder()
    c.folders.set_base_generators(tmp_folder)
    c.folders.generators = "."
    c.folders.set_base_build(tmp_folder)
    return c


def test_cmake_make_program(conanfile):
    def run(command):
        assert '-DCMAKE_MAKE_PROGRAM="C:/mymake.exe"' in command

    conanfile.run = run
    conanfile.conf.define("tools.gnu:make_program", "C:\\mymake.exe")

    with mock.patch("platform.system", mock.MagicMock(return_value='Windows')):
        write_cmake_presets(conanfile, "the_toolchain.cmake", "MinGW Makefiles", {})

    cmake = CMake(conanfile)
    cmake.configure()

