import unittest

from mock import Mock

from conans.client.conf import get_default_settings_yml
from conans.client.generators.pkg_config import PkgConfigGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings


class PkgGeneratorTest(unittest.TestCase):

    def test_variables_setup(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder1")
        cpp_info.filter_empty = False
        cpp_info.name = "my_pkg"
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("MyPkg1/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder1")
        cpp_info.filter_empty = False
        cpp_info.name = "MYPKG1"
        cpp_info.defines = ["MYDEFINE11"]
        cpp_info.cflags.append("-Flag1=21")
        cpp_info.version = "1.7"
        cpp_info.description = "My other cool description"
        cpp_info.public_deps = ["MyPkg"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder2")
        cpp_info.filter_empty = False
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cxxflags = ["-cxxflag"]
        cpp_info.public_deps = ["MyPkg"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = PkgConfigGenerator(conanfile)
        files = generator.content

        self.assertEqual(files["MyPkg2.pc"], """prefix=/dummy_root_folder2
libdir=${prefix}/lib
includedir=${prefix}/include

Name: MyPkg2
Description: Conan package: MyPkg2
Version: 2.3
Libs: -L"${libdir}" -sharedlinkflag -exelinkflag
Cflags: -I"${includedir}" -cxxflag -DMYDEFINE2
Requires: my_pkg
""")

        self.assertEqual(files["mypkg1.pc"], """prefix=/dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: mypkg1
Description: My other cool description
Version: 1.7
Libs: -L"${libdir}"
Cflags: -I"${includedir}" -Flag1=21 -DMYDEFINE11
Requires: my_pkg
""")

        self.assertEqual(files["my_pkg.pc"], """prefix=/dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: my_pkg
Description: My cool description
Version: 1.3
Libs: -L"${libdir}"
Cflags: -I"${includedir}" -Flag1=23 -DMYDEFINE1
""")

    def test_pkg_config_custom_names(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())

        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder1")
        cpp_info.filter_empty = False
        cpp_info.name = "my_pkg"
        cpp_info.names["pkg_config"] = "my_pkg_custom_name"
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("MyPkg1/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder1")
        cpp_info.filter_empty = False
        cpp_info.name = "MYPKG1"
        cpp_info.names["pkg_config"] = "my_pkg1_custom_name"
        cpp_info.defines = ["MYDEFINE11"]
        cpp_info.cflags.append("-Flag1=21")
        cpp_info.version = "1.7"
        cpp_info.description = "My other cool description"
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder2")
        cpp_info.filter_empty = False
        cpp_info.names["pkg_config"] = "my_pkg2_custom_name"
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cxxflags = ["-cxxflag"]
        cpp_info.public_deps = ["MyPkg", "MyPkg1"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("zlib/1.2.11@lasote/stable")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder_zlib")
        cpp_info.filter_empty = False
        cpp_info.name = "ZLIB"
        cpp_info.defines = ["MYZLIBDEFINE2"]
        cpp_info.version = "1.2.11"
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("bzip2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder2")
        cpp_info.filter_empty = False
        cpp_info.name = "BZip2"
        cpp_info.names["pkg_config"] = "BZip2"
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cxxflags = ["-cxxflag"]
        cpp_info.public_deps = ["MyPkg", "MyPkg1", "zlib"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = PkgConfigGenerator(conanfile)
        files = generator.content

        self.assertEqual(files["my_pkg2_custom_name.pc"], """prefix=/dummy_root_folder2
libdir=${prefix}/lib
includedir=${prefix}/include

Name: my_pkg2_custom_name
Description: Conan package: my_pkg2_custom_name
Version: 2.3
Libs: -L"${libdir}" -sharedlinkflag -exelinkflag
Cflags: -I"${includedir}" -cxxflag -DMYDEFINE2
Requires: my_pkg_custom_name my_pkg1_custom_name
""")
        self.assertEqual(files["my_pkg1_custom_name.pc"], """prefix=/dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: my_pkg1_custom_name
Description: My other cool description
Version: 1.7
Libs: -L"${libdir}"
Cflags: -I"${includedir}" -Flag1=21 -DMYDEFINE11
""")
        self.assertEqual(files["my_pkg_custom_name.pc"], """prefix=/dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: my_pkg_custom_name
Description: My cool description
Version: 1.3
Libs: -L"${libdir}"
Cflags: -I"${includedir}" -Flag1=23 -DMYDEFINE1
""")
        self.assertEqual(files["BZip2.pc"], """prefix=/dummy_root_folder2
libdir=${prefix}/lib
includedir=${prefix}/include

Name: BZip2
Description: Conan package: BZip2
Version: 2.3
Libs: -L"${libdir}" -sharedlinkflag -exelinkflag
Cflags: -I"${includedir}" -cxxflag -DMYDEFINE2
Requires: my_pkg_custom_name my_pkg1_custom_name zlib
""")

    def test_apple_frameworks(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = "apple-clang"
        settings.os = "Macos"
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.settings = settings
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "/dummy_root_folder1")
        cpp_info.filter_empty = False
        cpp_info.frameworks = ['AudioUnit', 'AudioToolbox']
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        generator = PkgConfigGenerator(conanfile)
        files = generator.content

        self.assertEqual(files["MyPkg.pc"], """prefix=/dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: MyPkg
Description: My cool description
Version: 1.3
Libs: -L"${libdir}" -Wl,-rpath,"${libdir}" -framework AudioUnit -framework AudioToolbox -F /dummy_root_folder1/Frameworks
Cflags: -I"${includedir}"
""")
