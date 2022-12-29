import json
import os
import unittest

from mock import Mock

from conans.client.generators.json_generator import JsonGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues, EnvInfo
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.model.user_info import UserInfo, DepsUserInfo


class JsonTest(unittest.TestCase):

    def test_variables_setup(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())

        # Add some cpp_info for dependencies
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"
        cpp_info.build_modules.append("cmake/module.cmake")
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cxxflags = ["-cxxflag"]
        cpp_info.public_deps = ["MyPkg"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        # Add env_info
        env_info = EnvInfo()
        env_info.VAR1 = "env_info-value1"
        env_info.PATH.append("path-extended")
        conanfile.deps_env_info.update(env_info, "env_info_pkg")

        # Add user_info
        user_info = UserInfo()
        user_info.VAR1 = "user_info-value1"
        conanfile.deps_user_info["user_info_pkg"] = user_info

        # Add user_info_build
        conanfile.user_info_build = DepsUserInfo()
        user_info = UserInfo()
        user_info.VAR1 = "user_info_build-value1"
        conanfile.user_info_build["user_info_build_pkg"] = user_info

        generator = JsonGenerator(conanfile)
        json_out = generator.content
        parsed = json.loads(json_out)

        # Check dependencies
        dependencies = parsed["dependencies"]
        self.assertEqual(len(dependencies), 2)
        my_pkg = dependencies[0]
        self.assertEqual(my_pkg["name"], "MyPkg")
        self.assertEqual(my_pkg["description"], "My cool description")
        self.assertEqual(my_pkg["defines"], ["MYDEFINE1"])
        self.assertListEqual(my_pkg["build_modules"]["cmake"], ["cmake/module.cmake"])
        self.assertListEqual(my_pkg["build_modules"]["cmake_multi"], ["cmake/module.cmake"])
        self.assertListEqual(my_pkg["build_modules"]["cmake_find_package"], ["cmake/module.cmake"])
        self.assertListEqual(my_pkg["build_modules"]["cmake_find_package_multi"],
                             ["cmake/module.cmake"])
        self.assertListEqual(my_pkg["build_modules_paths"]["cmake"],
                             [os.path.join("dummy_root_folder1", "cmake/module.cmake")])
        self.assertListEqual(my_pkg["build_modules_paths"]["cmake_multi"],
                             [os.path.join("dummy_root_folder1", "cmake/module.cmake")])
        self.assertListEqual(my_pkg["build_modules_paths"]["cmake_find_package"],
                             [os.path.join("dummy_root_folder1", "cmake/module.cmake")])
        self.assertListEqual(my_pkg["build_modules_paths"]["cmake_find_package_multi"],
                             [os.path.join("dummy_root_folder1", "cmake/module.cmake")])


        # Check env_info
        env_info = parsed["deps_env_info"]
        self.assertListEqual(sorted(env_info.keys()), sorted(["VAR1", "PATH"]))
        self.assertEqual(env_info["VAR1"], "env_info-value1")
        self.assertListEqual(env_info["PATH"], ["path-extended"])

        # Check user_info
        user_info = parsed["deps_user_info"]
        self.assertListEqual(list(user_info.keys()), ["user_info_pkg"])
        self.assertListEqual(list(user_info["user_info_pkg"].keys()), ["VAR1"])
        self.assertEqual(user_info["user_info_pkg"]["VAR1"], "user_info-value1")

        # Check user_info_build
        user_info_build = parsed["user_info_build"]
        self.assertListEqual(list(user_info_build.keys()), ["user_info_build_pkg"])
        self.assertListEqual(list(user_info_build["user_info_build_pkg"].keys()), ["VAR1"])
        self.assertEqual(user_info_build["user_info_build_pkg"]["VAR1"], "user_info_build-value1")
