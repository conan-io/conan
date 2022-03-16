import pytest
from mock import mock
from mock.mock import Mock

from conan.tools.cmake import CMake
from conan.tools.files.files import save_toolchain_args
from conans.model.conan_file import ConanFile
from conans.model.conf import Conf
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder


@pytest.fixture(scope="module")
def conanfile():
    c = ConanFile(Mock())
    c.settings = Settings({"os": ["Windows"],
                           "compiler": {"gcc": {"libcxx": ["libstdc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]})
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
    save_toolchain_args({"cmake_generator": "MinGW Makefiles"},
                        generators_folder=conanfile.folders.generators_folder)

    def run(command):
        assert '-DCMAKE_MAKE_PROGRAM="C:/mymake.exe"' in command

    conanfile.run = run
    conanfile.conf.define("tools.gnu:make_program", "C:\\mymake.exe")
    with mock.patch("platform.system", mock.MagicMock(return_value='Windows')):
        cmake = CMake(conanfile)
        cmake.configure()
