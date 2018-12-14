import json
import os
import unittest

from conans.client.generators.json_generator import JsonGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.tools import TestClient


class JsonTest(unittest.TestCase):

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
        generator = JsonGenerator(conanfile)
        json_out = generator.content

        parsed = json.loads(json_out)
        dependencies = parsed["dependencies"]
        self.assertEquals(len(dependencies), 2)
        my_pkg = dependencies[0]
        self.assertEquals(my_pkg["name"], "MyPkg")
        self.assertEquals(my_pkg["description"], "My cool description")
        self.assertEquals(my_pkg["defines"], ["MYDEFINE1"])
