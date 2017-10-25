import unittest

from conans.client.generators.boostbuild import BoostBuildGenerator
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference


class BoostJamGeneratorTest(unittest.TestCase):

    def variables_setup_test(self):

        conanfile = ConanFile(None, None, Settings({}), None)

        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"
        cpp_info.libs = ["MyLib1"]

        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.libs = ["MyLib2"]
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cppflags = ["-cppflag"]
        cpp_info.public_deps = ["MyPkg"]
        cpp_info.lib_paths.extend(["Path\\with\\slashes", "regular/path/to/dir"])
        cpp_info.include_paths.extend(["other\\Path\\with\\slashes", "other/regular/path/to/dir"])
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = BoostBuildGenerator(conanfile)

        self.assertEquals(generator.content, """lib MyLib1 :
	: # requirements
	<name>MyLib1
	: # default-build
	: # usage-requirements
	<define>MYDEFINE1
	<cflags>-Flag1=23
	;

lib MyLib2 :
	: # requirements
	<name>MyLib2
	<search>Path/with/slashes
	<search>regular/path/to/dir
	: # default-build
	: # usage-requirements
	<define>MYDEFINE2
	<include>other/Path/with/slashes
	<include>other/regular/path/to/dir
	<cxxflags>-cppflag
	<ldflags>-sharedlinkflag
	;

alias conan-deps :
	MyLib1
	MyLib2
;
""")
