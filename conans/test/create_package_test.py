import unittest
import os
from conans.test.tools import TestClient, TestBufferConanOutput
from conans.test.utils.test_files import hello_source_files
from conans.client.manager import CONANFILE
from conans.model.ref import ConanFileReference, PackageReference
import shutil
from conans.paths import CONANINFO
from conans.client.packager import create_package
from conans.client.loader import ConanFileLoader
from conans.model.options import OptionsValues
from conans.model.settings import Settings
from conans.client.output import ScopedOutput


myconan1 = """
from conans import ConanFile
import platform

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
    files = '*'

    def package(self):
        self.copy("*", "include", "include/math")
        self.copy("include/physics/*.hpp")
        self.copy("contrib/*", "include")
        self.copy("include/opencv/*")
        self.copy("include/opencv2/*")
        self.copy("*", "include", "modules/simu/include")
        self.copy("*", "include", "modules/3D/include")
        self.copy("*", "include", "modules/dev/include")
        self.copy("*.a", "lib/my_lib", "my_lib/debug")
        self.copy("*.txt", "res/shares", "my_data")

"""


class ExporterTest(unittest.TestCase):

    def complete_test(self):
        """ basic installation of a new conans
        """
        client = TestClient()
        client.init_dynamic_vars()
        files = hello_source_files()

        conan_ref = ConanFileReference.loads("Hello/1.2.1/frodo/stable")
        reg_folder = client.paths.export(conan_ref)

        client.save(files, path=reg_folder)
        client.save({CONANFILE: myconan1,
                     CONANINFO: "//empty",
                     "include/no_copy/lib0.h":                     "NO copy",
                     "include/math/lib1.h":                        "copy",
                     "include/math/lib2.h":                        "copy",
                     "include/physics/lib.hpp":                    "copy",
                     "my_lib/debug/libd.a":                        "copy",
                     "my_data/readme.txt":                         "copy",
                     "my_data/readme.md":                          "NO copy",
                     "contrib/math/math.h":                        "copy",
                     "contrib/physics/gravity.h":                  "copy",
                     "contrib/contrib.h":                          "copy",
                     "include/opencv/opencv.hpp":                  "copy",
                     "include/opencv2/opencv2.hpp":                "copy",
                     "modules/simu/src/simu.cpp":                  "NO copy",
                     "modules/simu/include/opencv2/simu/simu.hpp": "copy",
                     "modules/3D/doc/readme.md":                   "NO copy",
                     "modules/3D/include/opencv2/3D/3D.hpp":       "copy",
                     "modules/dev/src/dev.cpp":                    "NO copy",
                     "modules/dev/include/opencv2/dev/dev.hpp":    "copy",
                     "modules/opencv_mod.hpp":                     "copy"}, path=reg_folder)

        conanfile_path = os.path.join(reg_folder, CONANFILE)
        package_ref = PackageReference(conan_ref, "myfakeid")
        build_folder = client.paths.build(package_ref)
        package_folder = client.paths.package(package_ref)

        shutil.copytree(reg_folder, build_folder)

        loader = ConanFileLoader(None, Settings(), OptionsValues.loads(""))
        conanfile = loader.load_conan(conanfile_path, None)
        output = ScopedOutput("", TestBufferConanOutput())
        create_package(conanfile, build_folder, package_folder, output)

        # test build folder
        self.assertTrue(os.path.exists(build_folder))
        self.assertTrue(os.path.exists(os.path.join(package_folder, CONANINFO)))

        # test pack folder
        self.assertTrue(os.path.exists(package_folder))

        def exist(rel_path):
            return os.path.exists(os.path.join(package_folder, rel_path))

        # Expected files
        self.assertTrue(exist("include/lib1.h"))
        self.assertTrue(exist("include/lib2.h"))
        self.assertTrue(exist("include/physics/lib.hpp"))
        self.assertTrue(exist("include/contrib/math/math.h"))
        self.assertTrue(exist("include/contrib/physics/gravity.h"))
        self.assertTrue(exist("include/contrib/contrib.h"))
        self.assertTrue(exist("include/opencv/opencv.hpp"))
        self.assertTrue(exist("include/opencv2/opencv2.hpp"))
        self.assertTrue(exist("include/opencv2/simu/simu.hpp"))
        self.assertTrue(exist("include/opencv2/3D/3D.hpp"))
        self.assertTrue(exist("include/opencv2/dev/dev.hpp"))
        self.assertTrue(exist("lib/my_lib/libd.a"))
        self.assertTrue(exist("res/shares/readme.txt"))

        # Not expected files
        self.assertFalse(exist("include/opencv2/opencv_mod.hpp"))
        self.assertFalse(exist("include/opencv2/simu.hpp"))
        self.assertFalse(exist("include/opencv2/3D.hpp"))
        self.assertFalse(exist("include/opencv2/dev.hpp"))
        self.assertFalse(exist("include/modules/simu/src/simu.cpp"))
        self.assertFalse(exist("include/modules/3D/doc/readme.md"))
        self.assertFalse(exist("include/modules/dev/src/dev.cpp"))
        self.assertFalse(exist("include/opencv2/opencv_mod.hpp"))
        self.assertFalse(exist("include/include/no_copy/lib0.h"))
        self.assertFalse(exist("res/my_data/readme.md"))
