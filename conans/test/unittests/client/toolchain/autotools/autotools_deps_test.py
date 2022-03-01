import os
import platform
from collections import OrderedDict

import mock
from mock import Mock

from conan.tools.gnu import AutotoolsDeps
from conans import ConanFile
from conans.model.build_info import CppInfo
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import ConanFileDependencies, Requirement
from conans.model.ref import ConanFileReference
from conans.test.utils.mocks import MockSettings
from conans.test.utils.test_files import temp_folder


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


def test_foo():
    dep1 = ConanFile(Mock(), None)
    dep1.cpp_info = get_cpp_info("dep1")
    dep1._conan_node = Mock()
    dep1._conan_node.ref = ConanFileReference.loads("dep1/1.0")
    dep1.folders.set_base_package("/path/to/folder_dep1")

    dep2 = ConanFile(Mock(), None)
    dep2.cpp_info = get_cpp_info("dep2")
    dep2._conan_node = Mock()
    dep2._conan_node.ref = ConanFileReference.loads("dep2/1.0")
    dep2.folders.set_base_package("/path/to/folder_dep2")

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
             "os": "Macos",
             "compiler": "gcc",
             "compiler.libcxx": "libstdc++11",
             "compiler.version": "7.1",
             "cppstd": "17"})
        deps = AutotoolsDeps(consumer)

        env = deps.environment

        # Customize the environment
        env.remove("LDFLAGS", "dep2_shared_link_flag")
        env.remove("LDFLAGS", "-F /path/to/folder_dep1/one/framework/path/dep1")
        env.append("LDFLAGS", "OtherSuperStuff")

        env = deps.vars()
        # The contents are of course modified
        assert env["LDFLAGS"] == 'dep1_shared_link_flag ' \
                                 'dep1_exe_link_flag dep2_exe_link_flag ' \
                                 '-framework dep1_oneframework -framework dep1_twoframework ' \
                                 '-framework dep2_oneframework -framework dep2_twoframework ' \
                                 '-F /path/to/folder_dep2/one/framework/path/dep2 ' \
                                 '-L/path/to/folder_dep1/one/lib/path/dep1 ' \
                                 '-L/path/to/folder_dep2/one/lib/path/dep2 ' \
                                 '--sysroot=/path/to/folder/dep1 OtherSuperStuff'

        assert env["CXXFLAGS"] == 'dep1_a_cxx_flag dep2_a_cxx_flag --sysroot=/path/to/folder/dep1'
        assert env["CFLAGS"] == 'dep1_a_c_flag dep2_a_c_flag --sysroot=/path/to/folder/dep1'
        assert env["LIBS"] == "-ldep1_onelib -ldep1_twolib -ldep2_onelib -ldep2_twolib "\
                              "-ldep1_onesystemlib -ldep1_twosystemlib "\
                              "-ldep2_onesystemlib -ldep2_twosystemlib"

        folder = temp_folder()
        consumer.folders.set_base_install(folder)
        deps.generate()
        extension = ".bat" if platform.system() == "Windows" else ".sh"

        # The generated file also contains the changes
        with open(os.path.join(folder, "conanautotoolsdeps{}".format(extension))) as _f:
            contents = _f.read()
            assert "path/to/folder_dep1/one/framework/path/dep1" not in contents
            assert "OtherSuperStuff" in contents
