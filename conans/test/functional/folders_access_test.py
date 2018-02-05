import unittest

import os

from conans.test.utils.tools import TestClient
from conans.util.files import mkdir

conanfile_parent = """
from conans import ConanFile


class parentLib(ConanFile):

    name = "parent"
    version = "1.0"
    
    def package_info(self):
        self.cpp_info.cppflags.append("-myflag")
        self.user_info.MyVar = "MyVarValue"
        self.env_info.MyEnvVar = "MyEnvVarValue"

"""


conanfile = """
import os
from conans import ConanFile

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
    
    def assert_in_local_cache(self):
        if self.running_local_command:
            assert(self.in_local_cache == False)
   
    def source(self):
        assert(self.source_folder == os.getcwd())
        self.assert_in_local_cache()
        
        # Prevented to use them, it's dangerous, because the source is run only for the first
        # config, so only the first build_folder/package_folder would be modified
        assert(self.build_folder is None)
        assert(self.package_folder is None)
                        
        assert(self.source_folder is not None)
        self.copy_source_folder = self.source_folder
        
        if %(source_with_infos)s:
            self.assert_deps_infos()

    def assert_deps_infos(self):
        assert(self.deps_user_info["parent"].MyVar == "MyVarValue")
        assert(self.deps_cpp_info["parent"].cppflags[0] == "-myflag")
        assert(self.deps_env_info["parent"].MyEnvVar == "MyEnvVarValue")

    def build(self):
        assert(self.build_folder == os.getcwd())
        
        self.assert_in_local_cache()
        self.assert_deps_infos()
        
        if self.no_copy_source and self.in_local_cache:
            assert(self.copy_source_folder == self.source_folder)  # Only in install
            assert(self.install_folder == self.build_folder)
        else:
            assert(self.source_folder == self.build_folder)
            self.install_folder

        assert(self.package_folder is not None)
        self.copy_build_folder = self.build_folder
        
    def package(self):
        assert(self.install_folder is not None)

        if self.no_copy_source:
            # First call with source, second with build
            if self.counter_package_calls == 0:
               assert(self.source_folder == os.getcwd())
               self.counter_package_calls += 1
            elif self.counter_package_calls == 1:
               assert(self.build_folder == os.getcwd()) 
        else:
            assert(self.build_folder == os.getcwd())
    
        self.assert_in_local_cache()
        self.assert_deps_infos()
    
        
        if self.in_local_cache:
            assert(self.copy_build_folder == self.build_folder)

        if self.no_copy_source and self.in_local_cache:
            assert(self.copy_source_folder == self.source_folder)  # Only in install
        else:
            assert(self.source_folder == self.build_folder)
            
        self.copy_package_folder = self.package_folder
            
    def package_info(self):
        assert(self.package_folder == os.getcwd())
        assert(self.in_local_cache == True)
        
        assert(self.source_folder is None)
        assert(self.build_folder is None)
        assert(self.install_folder is None)

        
    def imports(self):
        assert(self.imports_folder == os.getcwd())
        
    def deploy(self):
        assert(self.install_folder == os.getcwd())

"""


class TestFoldersAccess(unittest.TestCase):
    """"Tests the presence of self.source_folder, self.build_folder, self.package_folder
    in the conanfile methods. Also the availability of the self.deps_cpp_info, self.deps_user_info
    and self.deps_env_info. Also the 'in_local_cache' variable. """

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile_parent})
        self.client.run("export . conan/stable")

    def source_local_command_test(self):
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("source .")

        c1 = conanfile % {"no_copy_source": True, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("source .")

        c1 = conanfile % {"no_copy_source": False, "source_with_infos": True,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        error = self.client.run("source .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("self.deps_user_info not defined. If you need it for a "
                      "local command run 'conan install'", self.client.out)

        # Now use infos to get the deps_cpp_info
        self.client.run("install . --build missing")
        self.client.run("source .")  # Default folder, not needed to specify --install-folder

        # Install in different location
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": True,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        old_dir = self.client.current_folder
        build_dir = os.path.join(self.client.current_folder, "build1")
        mkdir(build_dir)
        self.client.current_folder = build_dir
        self.client.run("install .. ")
        self.client.current_folder = old_dir
        self.client.run("source . --install-folder=build1")

    def build_local_command_test(self):

        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        error = self.client.run("build .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: conanbuildinfo.txt file not found", self.client.out)

        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("install . --build missing")
        self.client.run("build .")

        c1 = conanfile % {"no_copy_source": True, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("install . --build missing")
        self.client.run("build .")

    def package_local_command_test(self):
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        error = self.client.run("package .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: conanbuildinfo.txt file not found", self.client.out)

        self.client.run("install . --build missing")

        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("install . --build missing")
        self.client.run("package .")

    def imports_local_test(self):
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        error = self.client.run("imports .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: conanbuildinfo.txt file not found", self.client.out)

    def deploy_test(self):
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": True,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . user/testing --build missing")
        self.client.run("install lib/1.0@user/testing")  # Checks deploy

    def full_install_test(self):
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . conan/stable --build")

        c1 = conanfile % {"no_copy_source": True, "source_with_infos": False,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . conan/stable --build")

        c1 = conanfile % {"no_copy_source": False, "source_with_infos": True,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . conan/stable --build")

        c1 = conanfile % {"no_copy_source": True, "source_with_infos": True,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . conan/stable --build")