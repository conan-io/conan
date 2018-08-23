import os
import platform
import unittest

from conans.client.generators.pkg_config import PkgConfigGenerator
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.util.files import load
from conans.model.env_info import EnvValues


class PkgGeneratorTest(unittest.TestCase):

    def variables_setup_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
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

    def pkg_config_dirs_test(self):
        # https://github.com/conan-io/conan/issues/2756
        conanfile = """
import os
from conans import ConanFile

class PkgConfigConan(ConanFile):
    name = "MyLib"
    version = "0.1"

    def package_info(self):
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = []
        self.cpp_info.libs = []
        libname = "mylib"
        fake_dir = os.path.join("/", "my_absoulte_path", "fake")
        include_dir = os.path.join(fake_dir, libname, "include")
        lib_dir = os.path.join(fake_dir, libname, "lib")
        lib_dir2 = os.path.join(self.package_folder, "lib2")
        self.cpp_info.includedirs.append(include_dir)
        self.cpp_info.libdirs.append(lib_dir)
        self.cpp_info.libdirs.append(lib_dir2)
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . danimtb/testing")
        client.run("install MyLib/0.1@danimtb/testing -g pkg_config")

        pc_path = os.path.join(client.current_folder, "MyLib.pc")
        self.assertTrue(os.path.exists(pc_path))
        pc_content = load(pc_path)
        expected_rpaths = ""
        if platform.system() == "Linux":
            expected_rpaths = ' -Wl,-rpath="${libdir}" -Wl,-rpath="${libdir3}"'
        elif platform.system() == "Darwin":
            expected_rpaths = ' -Wl,-rpath,"${libdir}" -Wl,-rpath,"${libdir3}"'
        expected_content = """libdir=/my_absoulte_path/fake/mylib/lib
libdir3=${prefix}/lib2
includedir=/my_absoulte_path/fake/mylib/include

Name: MyLib
Description: Conan package: MyLib
Version: 0.1
Libs: -L${libdir} -L${libdir3}%s
Cflags: -I${includedir}""" % expected_rpaths
        self.assertEquals("\n".join(pc_content.splitlines()[1:]), expected_content)

        def assert_is_abs(path):
            self.assertTrue(os.path.isabs(path))

        for line in pc_content.splitlines():
            if line.startswith("includedir="):
                assert_is_abs(line[len("includedir="):])
                self.assertTrue(line.endswith("include"))
            elif line.startswith("libdir="):
                assert_is_abs(line[len("libdir="):])
                self.assertTrue(line.endswith("lib"))
            elif line.startswith("libdir3="):
                self.assertIn("${prefix}/lib2", line)

    def pkg_config_without_libdir_test(self):
        conanfile = """
import os
from conans import ConanFile

class PkgConfigConan(ConanFile):
    name = "MyLib"
    version = "0.1"

    def package_info(self):
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = []
        self.cpp_info.libs = []
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . danimtb/testing")
        client.run("install MyLib/0.1@danimtb/testing -g pkg_config")

        pc_path = os.path.join(client.current_folder, "MyLib.pc")
        self.assertTrue(os.path.exists(pc_path))
        pc_content = load(pc_path)
        self.assertEquals("\n".join(pc_content.splitlines()[1:]),
                          """
Name: MyLib
Description: Conan package: MyLib
Version: 0.1
Libs: 
Cflags: """)

    def pkg_config_rpaths_test(self):
        # rpath flags are only generated for gcc and clang
        profile = """
[settings]
os=Linux
compiler=gcc
compiler.version=7
compiler.libcxx=libstdc++
"""
        conanfile = """
from conans import ConanFile

class PkgConfigConan(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "os", "compiler"
    exports = "mylib.so"
    
    def package(self):
        self.copy("mylib.so", dst="lib")

    def package_info(self):
        self.cpp_info.libs = ["mylib"]
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "linux_gcc": profile,
                     "mylib.so": "fake lib content"})
        client.run("create . danimtb/testing -pr=linux_gcc")
        client.run("install MyLib/0.1@danimtb/testing -g pkg_config -pr=linux_gcc")

        pc_path = os.path.join(client.current_folder, "MyLib.pc")
        self.assertTrue(os.path.exists(pc_path))
        pc_content = load(pc_path)
        self.assertIn("-Wl,-rpath=\"${libdir}\"", pc_content)
