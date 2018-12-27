import os
import unittest

from conans.client import tools
from conans.client.conan_api import ConanAPIV1
from conans.test.utils.test_files import temp_folder


class PackageCommandTest(unittest.TestCase):

    def uses_recipe_env_test(self):
        tmp_folder = temp_folder()
        contents = conanfile.format(test_param=tmp_folder)
        tools.save(os.path.join(tmp_folder, "conanfile.py"), contents)
        api, _, _ = ConanAPIV1.factory()
        api.install(tmp_folder, install_folder=tmp_folder, env=["test_param=" + tmp_folder])
        # package will fail if recipe's environment is ignored
        api.package(tmp_folder, tmp_folder, os.path.join(tmp_folder, "package"))


conanfile = """\
from conans import ConanFile, tools

class Pkg(ConanFile):
    name = "lib"
    version = "1.0"

    def package(self):
        assert(tools.get_env("test_param") == "{test_param}")
"""
