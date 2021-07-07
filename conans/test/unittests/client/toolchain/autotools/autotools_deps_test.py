from collections import OrderedDict

import mock
import pytest
from mock import Mock

from conan.tools.gnu import AutotoolsDeps
from conans import ConanFile
from conans.model.build_info import CppInfo
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import ConanFileDependencies, Requirement
from conans.model.ref import ConanFileReference
from conans.test.utils.mocks import MockSettings


def get_cpp_info(name):
    cppinfo = CppInfo("{}/1.0".format(name), "/tmp/root")
    cppinfo.includedirs = []
    cppinfo.includedirs.append("path/includes/{}".format(name))
    cppinfo.includedirs.append("other\\include\\path\\{}".format(name))
    # To test some path in win, to be used with MinGW make or MSYS etc
    cppinfo.libdirs = []
    cppinfo.libdirs.append("one\\lib\\path\\{}".format(name))
    cppinfo.libs = []
    cppinfo.libs.append("{}_onelib".format(name))
    cppinfo.libs.append("{}_twolib".format(name))
    cppinfo.defines = []
    cppinfo.defines.append("{}_onedefinition".format(name))
    cppinfo.defines.append("{}_twodefinition".format(name))
    cppinfo.cflags = ["{}_a_c_flag".format(name)]
    cppinfo.cxxflags = ["{}_a_cxx_flag".format(name)]
    cppinfo.sharedlinkflags = ["{}_shared_link_flag".format(name)]
    cppinfo.exelinkflags = ["{}_exe_link_flag".format(name)]
    cppinfo.sysroot = "/path/to/folder/{}".format(name)
    cppinfo.frameworks = []
    cppinfo.frameworks.append("{}_oneframework".format(name))
    cppinfo.frameworks.append("{}_twoframework".format(name))
    cppinfo.system_libs = []
    cppinfo.system_libs.append("{}_onesystemlib".format(name))
    cppinfo.system_libs.append("{}_twosystemlib".format(name))
    cppinfo.frameworkdirs = []
    cppinfo.frameworkdirs.append("one/framework/path/{}".format(name))
    return cppinfo


@pytest.fixture
def dep1():
    dep1 = ConanFile(Mock(), None)
    dep1.cpp_info = get_cpp_info("dep1")
    dep1._conan_node = Mock()
    dep1._conan_node.ref = ConanFileReference.loads("dep1/1.0")
    dep1.package_folder = "/path/to/folder_dep1"
    return dep1


@pytest.fixture
def dep2():
    dep2 = ConanFile(Mock(), None)
    dep2.cpp_info = get_cpp_info("dep2")
    dep2._conan_node = Mock()
    dep2._conan_node.ref = ConanFileReference.loads("dep2/1.0")
    dep2.package_folder = "/path/to/folder_dep2"
    return dep2


def test_calculate_environment(dep1, dep2):

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req1 = Requirement(ConanFileReference.loads("dep1/1.0"))
        req2 = Requirement(ConanFileReference.loads("dep2/1.0"))
        deps = OrderedDict()
        deps[req1] = ConanFileInterface(dep1)
        deps[req2] = ConanFileInterface(dep2)
        mock_deps.return_value = ConanFileDependencies(deps)
        consumer = ConanFile(Mock(), None)
        consumer.settings = MockSettings(
            {"build_type": "Release",
             "arch": "x86",
             "compiler": "gcc",
             "compiler.libcxx": "libstdc++11",
             "compiler.version": "7.1",
             "cppstd": "17"})
        deps = AutotoolsDeps(consumer)
        # deps.generate()
        assert deps.environment["LDFLAGS"] == 'dep1_shared_link_flag dep2_shared_link_flag ' \
                                 'dep1_exe_link_flag dep2_exe_link_flag ' \
                                 '-framework dep1_oneframework -framework dep1_twoframework ' \
                                 '-framework dep2_oneframework -framework dep2_twoframework ' \
                                 '-F /path/to/folder_dep1/one/framework/path/dep1 ' \
                                 '-F /path/to/folder_dep2/one/framework/path/dep2 ' \
                                 '-L/path/to/folder_dep1/one/lib/path/dep1 ' \
                                 '-L/path/to/folder_dep2/one/lib/path/dep2 ' \
                                 '-Wl,-rpath,"/path/to/folder_dep1/one/lib/path/dep1" ' \
                                 '-Wl,-rpath,"/path/to/folder_dep2/one/lib/path/dep2" ' \
                                 '--sysroot=/path/to/folder/dep1'

        assert deps.environment["CXXFLAGS"] == 'dep1_a_cxx_flag dep2_a_cxx_flag ' \
                                               '--sysroot=/path/to/folder/dep1'
        assert deps.environment["CFLAGS"] == 'dep1_a_c_flag dep2_a_c_flag ' \
                                             '--sysroot=/path/to/folder/dep1'


def test_adjust_before_generate(dep1, dep2):

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req1 = Requirement(ConanFileReference.loads("dep1/1.0"))
        req2 = Requirement(ConanFileReference.loads("dep2/1.0"))
        deps = OrderedDict()
        deps[req1] = ConanFileInterface(dep1)
        deps[req2] = ConanFileInterface(dep2)
        mock_deps.return_value = ConanFileDependencies(deps)
        consumer = ConanFile(Mock(), None)
        consumer.settings = MockSettings(
            {"build_type": "Release",
             "arch": "x86",
             "compiler": "gcc",
             "compiler.libcxx": "libstdc++11",
             "compiler.version": "7.1",
             "cppstd": "17"})
        deps = AutotoolsDeps(consumer)

        # We can access the cpp_info and modify it
        deps.cpp_info.includedirs = ["/other/includedir"]

        # Later we can access to the flags and modify them
        deps.cpp_flags.append("NewCppFlag")

        # !!! If we modify now the deps.cpp_info after accessing the cpp_flags it raises
        with pytest.raises(Exception) as execinfo:
            deps.cpp_info.includedirs = []
        assert str(execinfo.value) == "Error in AutotoolsDeps: You cannot access '.cpp_info' once " \
                                      "the flags have been calculated"

        # Even later modify the environment
        env = deps.environment

        # !!!! If we modify the flags after accesing the environment it raises
        with pytest.raises(Exception) as execinfo:
            deps.cpp_flags.clear()
        assert str(execinfo.value) == "Error in AutotoolsDeps: You cannot access the flags once " \
                                      "the environment has been calculated"

        assert env["CPPFLAGS"] == '-I/other/includedir -Ddep1_onedefinition -Ddep1_twodefinition ' \
                                  '-Ddep2_onedefinition -Ddep2_twodefinition NewCppFlag'

        assert env["CXXFLAGS"] == 'dep1_a_cxx_flag dep2_a_cxx_flag --sysroot=/path/to/folder/dep1'
        assert env["CFLAGS"] == 'dep1_a_c_flag dep2_a_c_flag --sysroot=/path/to/folder/dep1'
