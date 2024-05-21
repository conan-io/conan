import textwrap
import unittest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


conanfile_parent = """
from conan import ConanFile

class parentLib(ConanFile):
    name = "parent"
    version = "1.0"

    def package_info(self):
        self.cpp_info.cxxflags.append("-myflag")
        self.buildenv_info.define("MyEnvVar", "MyEnvVarValue")
"""


conanfile = """
import os
from conan import ConanFile
from pathlib import Path

class AConan(ConanFile):
    name = "lib"
    version = "1.0"

    # To save the folders and check later if the folder is the same
    copy_build_folder = None
    copy_source_folder = None
    copy_package_folder = None

    counter_package_calls = 0

    no_copy_source = %(no_copy_source)s
    requires = "parent/1.0@conan/stable"
    running_local_command = %(local_command)s

    def source(self):
        assert(self.source_folder == os.getcwd())
        assert(isinstance(self.source_path, Path))
        assert(str(self.source_path) == self.source_folder)

        # Prevented to use them, it's dangerous, because the source is run only for the first
        # config, so only the first build_folder/package_folder would be modified
        assert(self.build_folder is None)
        assert(self.package_folder is None)

        assert(self.source_folder is not None)
        self.copy_source_folder = self.source_folder

    def build(self):
        assert(self.build_folder == os.getcwd())
        assert(isinstance(self.build_path, Path))
        assert(str(self.build_path) == self.build_folder)

        if self.no_copy_source:
            assert(self.copy_source_folder == self.source_folder)  # Only in install
        else:
            assert(self.source_folder == self.build_folder)

        assert(self.package_folder is not None)
        assert(isinstance(self.package_path, Path))
        assert(str(self.package_path) == self.package_folder)
        self.copy_build_folder = self.build_folder

    def package(self):
        assert(self.build_folder == os.getcwd())
        assert(isinstance(self.build_path, Path))
        assert(str(self.build_path) == self.build_folder)

        if self.no_copy_source:
            assert(self.copy_source_folder == self.source_folder)  # Only in install
        else:
            assert(self.source_folder == self.build_folder)

        self.copy_package_folder = self.package_folder

    def package_info(self):
        assert(self.package_folder == os.getcwd())
        assert(isinstance(self.package_path, Path))
        assert(str(self.package_path) == self.package_folder)
"""


class TestFoldersAccess(unittest.TestCase):
    """"Tests the presence of self.source_folder, self.build_folder, self.package_folder
    in the conanfile methods. Also the availability of the self.deps_cpp_info, self.deps_user_info
    and self.deps_env_info."""

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile_parent})
        self.client.run("export . --user=conan --channel=stable")

    def test_source_local_command(self):
        c1 = conanfile % {"no_copy_source": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("source .")

        c1 = conanfile % {"no_copy_source": True,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("source .")

    def test_deploy(self):
        c1 = conanfile % {"no_copy_source": False,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . --user=user --channel=testing --build missing")
        self.client.run("install --requires=lib/1.0@user/testing")  # Checks deploy

    def test_full_install(self):
        c1 = conanfile % {"no_copy_source": False,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . --user=conan --channel=stable --build='*'")

        c1 = conanfile % {"no_copy_source": True,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . --user=conan --channel=stable --build='*'")

        c1 = conanfile % {"no_copy_source": False,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . --user=conan --channel=stable --build='*'")


class RecipeFolderTest(unittest.TestCase):
    recipe_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import load
        import os
        class Pkg(ConanFile):
            exports = "file.txt"
            def init(self):
                r = load(self, os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("INIT: {}".format(r))
            def set_name(self):
                r = load(self, os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("SET_NAME: {}".format(r))
            def configure(self):
                r = load(self, os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("CONFIGURE: {}".format(r))
            def requirements(self):
                r = load(self, os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("REQUIREMENTS: {}".format(r))
            def package(self):
                r = load(self, os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("PACKAGE: {}".format(r))
            def package_info(self):
                r = load(self, os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("PACKAGE_INFO: {}".format(r))
        """)

    def test_recipe_folder(self):
        client = TestClient()
        client.save({"conanfile.py": self.recipe_conanfile,
                     "file.txt": "MYFILE!"})
        client.run("export . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("INIT: MYFILE!", client.out)
        self.assertIn("SET_NAME: MYFILE!", client.out)
        client.save({}, clean_first=True)
        client.run("install --requires=pkg/0.1@user/testing --build='*'")
        self.assertIn("pkg/0.1@user/testing: INIT: MYFILE!", client.out)
        self.assertNotIn("SET_NAME", client.out)
        self.assertIn("pkg/0.1@user/testing: CONFIGURE: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/testing: REQUIREMENTS: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/testing: PACKAGE: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/testing: PACKAGE_INFO: MYFILE!", client.out)

    def test_local_flow(self):
        client = TestClient()
        client.save({"conanfile.py": self.recipe_conanfile,
                     "file.txt": "MYFILE!"})
        client.run("install .")
        self.assertIn("INIT: MYFILE!", client.out)
        self.assertIn("SET_NAME: MYFILE!", client.out)
        self.assertIn("conanfile.py: CONFIGURE: MYFILE!", client.out)
        self.assertIn("conanfile.py: REQUIREMENTS: MYFILE!", client.out)

    def test_editable(self):
        client = TestClient()
        client.save({"pkg/conanfile.py": self.recipe_conanfile,
                     "pkg/file.txt": "MYFILE!",
                     "consumer/conanfile.py":
                         GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("editable add pkg --name=pkg --version=0.1 --user=user --channel=stable")

        client.run("install consumer")
        client.assert_listed_require({"pkg/0.1@user/stable": "Editable"})
        self.assertIn("pkg/0.1@user/stable: INIT: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/stable: CONFIGURE: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/stable: REQUIREMENTS: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/stable: PACKAGE_INFO: MYFILE!", client.out)
