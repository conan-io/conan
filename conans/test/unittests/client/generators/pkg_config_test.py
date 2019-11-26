import unittest

from conans.client.conf import default_settings_yml
from conans.client.generators.pkg_config import PkgConfigGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.tools import TestBufferConanOutput


class PkgGeneratorTest(unittest.TestCase):

    def variables_setup_test(self):
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.name = "my_pkg"
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"
        conanfile.deps_cpp_info.update(cpp_info, ref.name)

        ref = ConanFileReference.loads("MyPkg1/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.name = "MYPKG1"
        cpp_info.defines = ["MYDEFINE11"]
        cpp_info.cflags.append("-Flag1=21")
        cpp_info.version = "1.7"
        cpp_info.description = "My other cool description"
        cpp_info.public_deps = ["MyPkg"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)

        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.name = ref.name
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cxxflags = ["-cxxflag"]
        cpp_info.public_deps = ["MyPkg"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = PkgConfigGenerator(conanfile)
        files = generator.content

        self.assertEqual(files["MyPkg2.pc"], """prefix=dummy_root_folder2
libdir=${prefix}/lib
includedir=${prefix}/include

Name: MyPkg2
Description: Conan package: MyPkg2
Version: 2.3
Libs: -L${libdir} -sharedlinkflag -exelinkflag
Cflags: -I${includedir} -cxxflag -DMYDEFINE2
Requires: MyPkg
""")

        self.assertEqual(files["mypkg1.pc"], """prefix=dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: mypkg1
Description: My other cool description
Version: 1.7
Libs: -L${libdir}
Cflags: -I${includedir} -Flag1=21 -DMYDEFINE11
Requires: MyPkg
""")

        self.assertEqual(files["my_pkg.pc"], """prefix=dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: my_pkg
Description: My cool description
Version: 1.3
Libs: -L${libdir}
Cflags: -I${includedir} -Flag1=23 -DMYDEFINE1
""")

    def apple_frameworks_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = "apple-clang"
        settings.os = "Macos"
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.settings = settings
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.name = ref.name
        cpp_info.frameworks = ['AudioUnit', 'AudioToolbox']
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"
        conanfile.deps_cpp_info.update(cpp_info, ref.name)

        generator = PkgConfigGenerator(conanfile)
        files = generator.content

        self.assertEqual(files["MyPkg.pc"], """prefix=dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: MyPkg
Description: My cool description
Version: 1.3
Libs: -L${libdir} -Wl,-rpath,"${libdir}" -framework AudioUnit -framework AudioToolbox
Cflags: -I${includedir}
""")
