import unittest

from conans.client.generators.pkg_config import PkgConfigGenerator
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference


class PkgGeneratorTest(unittest.TestCase):

    def variables_setup_test(self):

        conanfile = ConanFile(None, None, Settings({}), None)

        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"

        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cppflags = ["-cppflag"]
        cpp_info.public_deps = ["MyPkg"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = PkgConfigGenerator(conanfile)
        files = generator.content

        self.assertEquals(files["MyPkg2.pc"], """prefix=dummy_root_folder2
libdir=${prefix}/lib
includedir=${prefix}/include

Name: MyPkg2
Description: Conan package: MyPkg2
Version: 2.3
Libs: -L${libdir} -sharedlinkflag -exelinkflag
Cflags: -I${includedir} -cppflag -DMYDEFINE2
Requires: MyPkg
""")

        self.assertEquals(files["MyPkg.pc"], """prefix=dummy_root_folder1
libdir=${prefix}/lib
includedir=${prefix}/include

Name: MyPkg
Description: My cool description
Version: 1.3
Libs: -L${libdir}
Cflags: -I${includedir} -Flag1=23 -DMYDEFINE1
""")
