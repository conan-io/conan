import os
import platform
import unittest

from conans.client.generators.text import TXTGenerator
from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANINFO, CONANENV, BUILD_INFO
from conans.test.utils.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import load
from conans import tools
from nose.plugins.attrib import attr


class ConanEnvTest(unittest.TestCase):

    @attr('slow')
    def shared_in_current_directory_test(self):
        """
        - There is a package building a shared library
        - There is a consumer project importing the shared library (and the executable)
        - The consumer tries to execute the imported shared library and executable in the same
          directory, and it fails in Linux, but works on OSX and WIndows.
        - Then I move the shared library to a different directory, and it fails,
          I'm making sure that there is no harcoded rpaths messing.
        - Finally I use the virtualrunenvironment that declares de LD_LIBRARY_PATH,
          PATH and DYLD_LIBRARY_PATH to run the executable, and.. magic!
          it's running agains the shared in the local cache.
        """


        conanfile = """
from conans import ConanFile, CMake, tools


class LibConan(ConanFile):
    name = "lib"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False]}
    default_options = "shared=True"
    generators = "cmake"
    exports_sources = "*"

    def build(self):
        cmake = CMake(self)
        self.run('cmake %s' % cmake.command_line)
        self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        self.copy("*.h", dst="include", src="hello")
        self.copy("*.lib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)
        self.copy("*.so", dst="lib", keep_path=False)
        self.copy("*.dylib", dst="lib", keep_path=False)
        self.copy("*main*", dst="bin", keep_path=False)

"""
        cmakelists =  """
project(mytest)
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)

SET(CMAKE_SKIP_RPATH 1)
ADD_LIBRARY(hello SHARED hello.c)
ADD_EXECUTABLE(main main.c)
TARGET_LINK_LIBRARIES(main hello)
"""

        hello_h = """#pragma once
#ifdef WIN32
  #define HELLO_EXPORT __declspec(dllexport)
#else
  #define HELLO_EXPORT
#endif

HELLO_EXPORT void hello();
"""

        client = TestClient()
        files = {CONANFILE: conanfile,
                 "CMakeLists.txt": cmakelists,
                 "hello.c": '#include "hello.h"\nvoid hello(){\nreturn;}',
                 "hello.h": hello_h,
                 "main.c": '#include "hello.h"\nint main(){\nhello();\nreturn 0;\n}'}

        client.save(files)
        client.run("export . conan/stable")
        client.run("install lib/1.0@conan/stable -o lib:shared=True --build missing")
        client.save({"conanfile.txt": '''
[requires]
lib/1.0@conan/stable
[generators]
virtualrunenv
[imports]
bin, * -> ./bin
lib, * -> ./bin
'''}, clean_first=True)

        client.run("install .")
        # Break possible rpaths built in the exe with absolute paths
        os.rename(os.path.join(client.current_folder, "bin"),
                  os.path.join(client.current_folder, "bin2"))

        with tools.chdir(os.path.join(client.current_folder, "bin2")):
            if platform.system() == "Windows":
                self.assertEqual(os.system("main.exe"), 0)
            elif platform.system() == "Darwin":
                self.assertEqual(os.system("./main"), 0)
            else:
                self.assertNotEqual(os.system("./main"), 0)
                self.assertEqual(os.system("LD_LIBRARY_PATH=$(pwd) ./main"), 0)
                self.assertEqual(os.system("LD_LIBRARY_PATH=. ./main"), 0)

            # If we move the shared library it won't work, at least we use the virtualrunenv
            os.mkdir(os.path.join(client.current_folder, "bin2", "subdir"))
            name = {"Darwin": "libhello.dylib",
                    "Windows": "hello.dll"}.get(platform.system(), "libhello.so")

            os.rename(os.path.join(client.current_folder, "bin2", name),
                      os.path.join(client.current_folder, "bin2", "subdir", name))

            if platform.system() == "Windows":
                self.assertNotEqual(os.system("main.exe"), 0)
            elif platform.system() == "Darwin":
                self.assertNotEqual(os.system("./main"), 0)
            else:
                self.assertNotEqual(os.system("LD_LIBRARY_PATH=$(pwd) ./main"), 0)

            # Will use the shared from the local cache
            if platform.system() != "Windows":
                command = "bash -c 'source ../activate_run.sh && ./main'"
            else:
                command = "cd .. && activate_run.bat && cd bin2 && main.exe"

            self.assertEqual(os.system(command), 0)

    def test_package_env_working(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    version = "0.1"
"""
        test_conanfile = """from conans import ConanFile
import os
class MyTest(ConanFile):
    requires = "Pkg/0.1@lasote/testing"
    def build(self):
        self.output.warn('MYVAR==>%s' % os.environ.get('MYVAR', ""))
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . lasote/testing -e MYVAR=MYVALUE")
        self.assertIn("MYVAR==>MYVALUE", client.user_io.out)

    def deactivate_env_inheritance_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    def package_info(self):
        self.env_info.SOME_VAR.append("22")
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")

        conanfile = """from conans import ConanFile
import os
class MyLib(ConanFile):
    apply_env = False
    requires = "Pkg/0.1@lasote/testing"
    
    def _test(self):
        assert("SOME_VAR" not in os.environ)
        assert(self.deps_env_info["Pkg"].SOME_VAR == ["22"])
    
    def build(self):
        self._test()
        
    def package(self):
        self._test()
        
    def package_info(self):
        self._test()
    
    def build(self):
        self._test()
              
    def imports(self):
        self._test()     
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . MyLib/0.1@lasote/testing")

        # Now as a build require, should be the same
        client.save({"conanfile.py": conanfile.replace("requires =", "#requires ="),
                     "myprofile": "[build_requires]\nPkg/0.1@lasote/testing"})
        client.run("create . MyLib/0.1@lasote/testing --profile ./myprofile")

    def env_path_order_test(self):
        client = TestClient()
        with tools.environment_append({"SOME_VAR": ["INITIAL VALUE"]}):
            conanfile = """from conans import ConanFile
import os
class MyPkg(ConanFile):
    def build(self):
        self.output.info("PKG VARS: %s" % os.getenv("SOME_VAR"))
    def package_info(self):
        self.env_info.SOME_VAR.append("OTHER_VALUE")
"""
            client.save({"conanfile.py": conanfile})
            client.run("create . Pkg/0.1@lasote/testing")
            self.assertIn("Pkg/0.1@lasote/testing: PKG VARS: INITIAL VALUE", client.out)

            conanfile = """from conans import ConanFile
import os
class MyTest(ConanFile):
    requires = "Pkg/0.1@lasote/testing"
    def build(self):
        self.output.info("TEST VARS: %s" % os.getenv("SOME_VAR"))
    def package_info(self):
        self.env_info.SOME_VAR.extend(["OTHER_VALUE2", "OTHER_VALUE3"])
"""
            client.save({"conanfile.py": conanfile})
            client.run("create . Test/0.1@lasote/testing")
            # FIXME: Note that these values are os.pathsep (; or :)
            self.assertIn("Test/0.1@lasote/testing: TEST VARS: OTHER_VALUE%sINITIAL VALUE"
                          % os.pathsep,
                          client.out)
            conanfile = """from conans import ConanFile
import os
class MyTest(ConanFile):
    requires = "Test/0.1@lasote/testing"
    def build(self):
        self.output.info("PROJECT VARS: %s" % os.getenv("SOME_VAR"))
"""
            client.save({"conanfile.py": conanfile})
            client.run("create . project/0.1@lasote/testing")
            self.assertIn("project/0.1@lasote/testing: PROJECT VARS: " +
                          os.pathsep.join(["OTHER_VALUE2", "OTHER_VALUE3",
                                           "OTHER_VALUE", "INITIAL VALUE"]),
                          client.out)
            client.run("create . project/0.1@lasote/testing -e SOME_VAR=[WHAT]")
            self.assertIn("project/0.1@lasote/testing: PROJECT VARS: " +
                          os.pathsep.join(["WHAT", "OTHER_VALUE2", "OTHER_VALUE3",
                                           "OTHER_VALUE", "INITIAL VALUE"]),
                          client.out)

    def test_run_env(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile
from conans.tools import mkdir
import os

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    build_policy = "missing"

    def package_info(self):
        mkdir(os.path.join(self.package_folder, "bin2"))
        mkdir(os.path.join(self.package_folder, "lib2"))
        self.cpp_info.bindirs.append("bin2")
        self.cpp_info.libdirs.append("lib2")

'''
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")

        reuse = '''[requires]
Hello/0.1@lasote/stable
[generators]
virtualrunenv
'''

        client.save({"conanfile.txt": reuse}, clean_first=True)
        client.run("install .")

        ext = "bat" if platform.system() == "Windows" else "sh"
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "activate_run.%s" % ext)))
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "deactivate_run.%s" % ext)))
        activate_contents = load(os.path.join(client.current_folder, "activate_run.%s" % ext))

        self.assertIn("PATH", activate_contents)
        self.assertIn("LD_LIBRARY_PATH", activate_contents)
        self.assertIn("DYLD_LIBRARY_PATH", activate_contents)

        for line in activate_contents.splitlines():
            if " PATH=" in line:
                self.assertIn("bin2", line)
                self.assertNotIn("lib2", line)
            if " DYLD_LIBRARY_PATH=" in line:
                self.assertNotIn("bin2", line)
                self.assertIn("lib2", line)
            if " LD_LIBRARY_PATH=" in line:
                self.assertNotIn("bin2", line)
                self.assertIn("lib2", line)

    def dual_compiler_settings_and_env_test(self):

        def patch_conanfile(conanfile):
            return conanfile + '''
    def build(self):
        import os
        self.output.warn("COMPILER: %s=>%s" % (self.name, self.settings.compiler))
        self.output.warn("CXX: %s=>%s" % (self.name, os.environ["CXX"]))
        self.output.warn("CC: %s=>%s" % (self.name, os.environ["CC"]))
'''

        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "1.0", deps=[], build=False)
        files[CONANFILE] = patch_conanfile(files[CONANFILE])
        client.save(files)
        client.run("export . lasote/stable")

        files = cpp_hello_conan_files("Hello1", "1.0",
                                      deps=["Hello0/1.0@lasote/stable"], build=False)
        files[CONANFILE] = patch_conanfile(files[CONANFILE])
        client.save(files)
        client.run("export . lasote/stable")

        # Both with same settings
        client.run("install Hello1/1.0@lasote/stable --build -s compiler=gcc"
                   " -s compiler.version=4.6 -s compiler.libcxx=libstdc++11"
                   " -e CXX=/mycompilercxx -e CC=/mycompilercc")

        self.assertIn("COMPILER: Hello0=>gcc", client.user_io.out)
        self.assertIn("CXX: Hello0=>/mycompilercxx", client.user_io.out)
        self.assertIn("CC: Hello0=>/mycompilercc", client.user_io.out)

        self.assertIn("COMPILER: Hello1=>gcc", client.user_io.out)
        self.assertIn("CXX: Hello1=>/mycompilercxx", client.user_io.out)
        self.assertIn("CC: Hello1=>/mycompilercc", client.user_io.out)

        # Different for Hello0
        client.run("install Hello1/1.0@lasote/stable --build -s compiler=gcc"
                   " -s compiler.version=4.6 -s compiler.libcxx=libstdc++11"
                   " -e CXX=/mycompilercxx -e CC=/mycompilercc"
                   " -s Hello0:compiler=clang -s Hello0:compiler.version=3.7"
                   " -s Hello0:compiler.libcxx=libstdc++"
                   " -e Hello0:CXX=/othercompilercxx -e Hello0:CC=/othercompilercc")

        self.assertIn("COMPILER: Hello0=>clang", client.user_io.out)
        self.assertIn("CXX: Hello0=>/othercompilercxx", client.user_io.out)
        self.assertIn("CC: Hello0=>/othercompilercc", client.user_io.out)

        self.assertIn("COMPILER: Hello1=>gcc", client.user_io.out)
        self.assertIn("CXX: Hello1=>/mycompilercxx", client.user_io.out)
        self.assertIn("CC: Hello1=>/mycompilercc", client.user_io.out)

    def conan_profile_unscaped_env_var_test(self):

        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
'''
        files = {"conanfile.py": conanfile}
        client.save(files)
        client.run("export . lasote/stable")
        reuse = '''
[requires]
Hello/0.1@lasote/stable

[generators]
virtualenv
'''
        profile = '''
[env]
CXXFLAGS=-fPIC -DPIC

'''
        files = {"conanfile.txt": reuse, "myprofile": profile}
        client.save(files, clean_first=True)
        client.run("install . --profile ./myprofile --build missing")

        with tools.chdir(client.current_folder):
            if platform.system() != "Windows":
                ret = os.system("chmod +x activate.sh && ./activate.sh")
            else:
                ret = os.system("activate.bat")
        self.assertEquals(ret, 0)

    def conan_env_deps_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    def package_info(self):
        self.env_info.var1="bad value"
        self.env_info.var2.append("value2")
        self.env_info.var3="Another value"
        self.env_info.path = "/dir"
'''
        files = {"conanfile.py": conanfile}
        client.save(files)
        client.run("export . lasote/stable")
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello2"
    version = "0.1"
    def config(self):
        self.requires("Hello/0.1@lasote/stable")

    def package_info(self):
        self.env_info.var1="good value"
        self.env_info.var2.append("value3")
        self.env_info.CPPFLAGS.append("MYCPPFLAG=1")
    '''
        files["conanfile.py"] = conanfile
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Hello2/0.1@lasote/stable --build "
                   "-g virtualenv -e CPPFLAGS=[OtherFlag=2]")
        ext = "bat" if platform.system() == "Windows" else "sh"
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "activate.%s" % ext)))
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "deactivate.%s" % ext)))
        activate_contents = load(os.path.join(client.current_folder, "activate.%s" % ext))
        deactivate_contents = load(os.path.join(client.current_folder, "deactivate.%s" % ext))
        self.assertNotIn("bad value", activate_contents)
        if platform.system() == "Windows":
            self.assertIn("var1=good value", activate_contents)
        else:
            self.assertIn('var1="good value"', activate_contents)

        if platform.system() == "Windows":
            self.assertIn('var2=value3;value2;%var2%', activate_contents)
        else:
            self.assertIn('var2="value3":"value2":$var2', activate_contents)
            self.assertIn('CPPFLAGS="OtherFlag=2 MYCPPFLAG=1 $CPPFLAGS"', activate_contents)
        self.assertIn("Another value", activate_contents)
        if platform.system() == "Windows":
            self.assertIn("PATH=/dir", activate_contents)
        else:
            self.assertIn("PATH=\"/dir\"", activate_contents)

        self.assertIn('var1=', deactivate_contents)
        self.assertIn('var2=', deactivate_contents)

    def test_conan_info_cache_and_priority(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    def package_info(self):
        self.env_info.VAR1="99"
'''
        reuse = '''
import os
from conans import ConanFile

class Hello2Conan(ConanFile):
    requires="Hello/0.1@lasote/stable"

    def build(self):
        self.output.info("VAR1=>%s" % os.environ.get("VAR1"))

'''
        files = dict()
        files["conanfile.py"] = conanfile
        client.save(files)
        client.run("export . lasote/stable")

        files = dict()
        files["conanfile.py"] = reuse
        client.save(files)
        client.run("install . --build missing")
        client.run("build .")
        self.assertIn("VAR1=>99", client.user_io.out)

        # Now specify a different value in command Line, but conaninfo already exists
        # So you cannot override it from command line without deleting the conaninfo.TXTGenerator
        client.run("install . -e VAR1=100 --build missing")
        client.run("build .")
        self.assertIn("VAR1=>100", client.user_io.out)

        # Remove conaninfo
        os.remove(os.path.join(client.current_folder, CONANINFO))
        client.run("install . -e VAR1=100 --build missing")
        client.run("build .")
        self.assertIn("VAR1=>100", client.user_io.out)

        # Now from a profile
        os.remove(os.path.join(client.current_folder, CONANINFO))
        client.save({"myprofile": "[env]\nVAR1=102"}, clean_first=False)
        client.run("install . --profile ./myprofile --build missing")
        client.run("build .")
        self.assertIn("VAR1=>102", client.user_io.out)

    def test_complex_deps_propagation(self):
        client = TestClient()
        self._export(client, "A", [], {"VAR1": "900", "VAR2": "23"})
        self._export(client, "B1", ["A"], {"VAR1": "800", "VAR2": "24"})
        self._export(client, "B2", ["A"], {"VAR1": "700", "VAR3": "22"})
        self._export(client, "C", ["B1", "B2"], {})

        client.save({"conanfile.py": reuse})
        client.run("install . --build missing")
        client.run("build .")
        self.assertIn("VAR1=>800*", client.user_io.out)
        self.assertIn("VAR2=>24*", client.user_io.out)
        self.assertIn("VAR3=>22*", client.user_io.out)

    def assertInSep(self, string, output):
        string = string.replace(":", os.pathsep)
        self.assertIn(string, output)

    def replace_sep(self, string):
        return string.replace(":", os.pathsep)

    def test_complex_deps_propagation_append(self):
        client = TestClient()
        self._export(client, "A", [], {"VAR3": "-23"}, {"VAR1": "900", "VAR2": "23"})
        self._export(client, "B", ["A"], {}, {"VAR1": "800", "VAR2": "24"})
        self._export(client, "C", ["B"], {"VAR3": "45"}, {"VAR1": "700"})

        client.save({"conanfile.py": reuse})
        client.run("install . --build missing")
        client.run("build .")
        self.assertInSep("VAR1=>700:800:900*" % {"sep": os.pathsep}, client.user_io.out)
        self.assertInSep("VAR2=>24:23*" % {"sep": os.pathsep}, client.user_io.out)
        self.assertInSep("VAR3=>45*", client.user_io.out)

        # Try other configuration
        self._export(client, "A", [], {}, {"VAR1": "900", "VAR2": "23", "VAR3": "-23"})
        self._export(client, "B", ["A"], {}, {"VAR1": "800", "VAR2": "24"})
        self._export(client, "C", ["B"], {"VAR3": "23"}, {"VAR1": "700"})

        client.save({"conanfile.py": reuse})
        client.run("install . --build missing")
        client.run("build .")
        self.assertInSep("VAR1=>700:800:900*", client.user_io.out)
        self.assertInSep("VAR2=>24:23*", client.user_io.out)
        self.assertInSep("VAR3=>23*", client.user_io.out)

        # Try injecting some ENV in the install
        self._export(client, "A", [], {}, {"VAR1": "900", "VAR2": "23", "VAR3": "-23"})
        self._export(client, "B", ["A"], {}, {"VAR1": "800", "VAR2": "24"})
        self._export(client, "C", ["B"], {"VAR3": "23"}, {"VAR1": "700"})

        client.save({"conanfile.py": reuse})
        client.run("install . --build missing -e VAR1=[override] -e VAR3=SIMPLE")
        client.run("build .")
        self.assertInSep("VAR1=>override:700:800:900", client.user_io.out)
        self.assertInSep("VAR2=>24:23*", client.user_io.out)
        self.assertIn("VAR3=>SIMPLE*", client.user_io.out)

    def test_override_simple(self):
        client = TestClient()
        # Try injecting some package level ENV in the install
        self._export(client, "A", [], {}, {"VAR1": "900", "VAR2": "23", "VAR3": "-23"})
        self._export(client, "B", ["A"], {}, {"VAR1": "800", "VAR2": "24"})
        self._export(client, "C", ["B"], {}, {"VAR1": "700"})

        client.save({"conanfile.py": reuse})
        client.run("install . --build missing -e LIB_A:VAR3=override")
        client.run("build .")
        self.assertInSep("VAR1=>700:800:900", client.user_io.out)
        self.assertInSep("VAR2=>24:23*", client.user_io.out)
        self.assertIn("VAR3=>-23*", client.user_io.out)

    def test_override_simple2(self):
        client = TestClient()
        # Try injecting some package level ENV in the install
        self._export(client, "A", [], {"VAR3": "-23"}, {"VAR1": "900", "VAR2": "23"})
        self._export(client, "B", ["A"], {}, {"VAR1": "800", "VAR2": "24"})
        self._export(client, "C", ["B"], {}, {"VAR1": "700"})

        client.save({"conanfile.py": reuse})
        client.run("install . --build missing -e VAR3=override")
        self.assertIn("Building LIB_A, VAR1:None", client.user_io.out)
        self.assertIn("Building LIB_A, VAR2:None", client.user_io.out)
        self.assertIn("Building LIB_A, VAR3:override", client.user_io.out)

        self.assertIn("Building LIB_B, VAR1:900", client.user_io.out)
        self.assertIn("Building LIB_B, VAR2:23", client.user_io.out)
        self.assertIn("Building LIB_B, VAR3:override", client.user_io.out)

        self.assertIn("Building LIB_C, VAR1:800", client.user_io.out)
        self.assertIn("Building LIB_C, VAR2:24", client.user_io.out)
        self.assertIn("Building LIB_C, VAR3:override", client.user_io.out)

        client.run("build .")
        self.assertInSep("VAR1=>700:800:900", client.user_io.out)
        self.assertInSep("VAR2=>24:23*", client.user_io.out)
        self.assertInSep("VAR3=>override*", client.user_io.out)

    def test_complex_deps_propagation_override(self):
        client = TestClient()
        # Try injecting some package level ENV in the install, but without priority
        self._export(client, "A", [], {}, {"VAR1": "900", "VAR2": "23", "VAR3": "-23"})
        self._export(client, "B", ["A"], {}, {"VAR1": "800", "VAR2": "24"})
        self._export(client, "C", ["B"], {"VAR3": "bestvalue"}, {"VAR1": "700"})

        client.save({"conanfile.py": reuse})
        client.run("install . --build missing -e LIB_B:VAR3=override")
        self.assertIn("Building LIB_A, VAR1:None", client.user_io.out)
        self.assertIn("Building LIB_A, VAR2:None", client.user_io.out)
        self.assertIn("Building LIB_A, VAR3:None", client.user_io.out)

        self.assertIn("Building LIB_B, VAR1:900", client.user_io.out)
        self.assertIn("Building LIB_B, VAR2:23", client.user_io.out)
        self.assertIn("Building LIB_B, VAR3:override", client.user_io.out)

        self.assertIn("Building LIB_C, VAR1:800", client.user_io.out)
        self.assertIn("Building LIB_C, VAR2:24", client.user_io.out)
        self.assertIn("Building LIB_C, VAR3:-23", client.user_io.out)

        client.run("build .")
        self.assertInSep("VAR1=>700:800:900", client.user_io.out)
        self.assertInSep("VAR2=>24:23*", client.user_io.out)
        self.assertInSep("VAR3=>bestvalue*", client.user_io.out)


    def check_conaninfo_completion_test(self):
        """
        consumer -> B -> C
                      -> D (conditional)

        The overwritten environment variables caused by the consumer have to be reflected in B's conaninfo.txt
        """
        client = TestClient()
        conanfile = """
from conans import ConanFile
class LibConan(ConanFile):
    name = "libC"
    version = "1.0"

    def package_info(self):
        self.env_info.MYVAR = "ValueByLibC"
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . foo/bar")

        conanfile = """
from conans import ConanFile
class LibConan(ConanFile):
    name = "libD"
    version = "1.0"

    def package_info(self):
        self.env_info.MYVAR = "ValueByLibD"
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . foo/bar")

        conanfile = """
import os
from conans import ConanFile
class LibConan(ConanFile):
    name = "libB"
    version = "1.0"

    def requirements(self):
        if os.environ.get("DEP", None) == "C":
            self.requires.add("libC/1.0@foo/bar")
        else:
            self.requires.add("libD/1.0@foo/bar")

    def build_info(self):
        self.output.warn("Value of MYVAR: %s" % os.environ["MYVAR"])
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . foo/bar")

        refb = PackageReference.loads("libB/1.0@foo/bar:5fecb9aaf431791c8c06ab146f3451823f982bb8")

        # With no overrides, B takes dependency D and the value should be ValueByLibD
        client.run("install libB/1.0@foo/bar --build")
        self.assertTrue("Value of MYVAR: ValueByLibD")
        conaninfo = load(os.path.join(client.client_cache.package(refb), CONANINFO))
        self.assertTrue(conaninfo.endswith("[env]\n\n"))  # Not user input env

        # B takes dependency C and the value should be ValueByLibC
        client.run("install libB/1.0@foo/bar --build -e DEP=C")
        self.assertTrue("Value of MYVAR: ValueByLibC")
        conaninfo = load(os.path.join(client.client_cache.package(refb), CONANINFO))
        self.assertTrue(conaninfo.endswith("[env]\n\n"))  # Not user input env

        # Consumer overrides MYVAR, so his conaninfo should have it
        client.run("install libB/1.0@foo/bar --build -e MYVAR=ValueByConsumer")
        self.assertTrue("Value of MYVAR: ValueByConsumer")
        conaninfo = load(os.path.join(client.client_cache.package(refb), CONANINFO))
        self.assertTrue(conaninfo.endswith("[env]\n    MYVAR=ValueByConsumer\n"))

        # Consumer overrides MYVAR, so his conaninfo should have it, but not the libC, because
        # is not a dependency
        client.run("install libB/1.0@foo/bar --build -e libB:MYVAR=ValueByConsumer "
                   "-e libC:MYVAR=OtherValue")
        self.assertTrue("Value of MYVAR: ValueByConsumer")
        conaninfo = load(os.path.join(client.client_cache.package(refb), CONANINFO))
        self.assertTrue(conaninfo.endswith("[env]\n    libB:MYVAR=ValueByConsumer\n"))

        # Consumer overrides MYVAR, so his conaninfo should have it, both libB and libD
        client.run("install libB/1.0@foo/bar --build -e libB:MYVAR=ValueByConsumer "
                   "-e libD:MYVAR=OtherValue")
        self.assertTrue("Value of MYVAR: ValueByConsumer")
        conaninfo = load(os.path.join(client.client_cache.package(refb), CONANINFO))
        self.assertTrue(conaninfo.endswith("[env]\n    libB:MYVAR=ValueByConsumer\n"
                                           "    libD:MYVAR=OtherValue\n"))  # Not user input env

    def test_conaninfo_filtered(self):
        client = TestClient()
        # Try injecting some package level ENV in the install, but without priority
        self._export(client, "A", [], {}, {"VAR1": "900", "VAR2": "23", "VAR3": "-23"})
        self._export(client, "B", ["A"], {}, {"VAR1": "800", "VAR2": "24"})
        self._export(client, "B2", ["A"], {}, {"VAR1": "800_2", "VAR2": "24_2"})
        self._export(client, "C", ["B", "B2"], {"VAR3": "bestvalue"}, {"VAR1": "700"})

        def load_conaninfo(lib):
            # Read the LIB_A conaninfo
            packages_path = client.client_cache.packages(ConanFileReference.loads("LIB_%s/1.0@lasote/stable" % lib))
            package_path = os.path.join(packages_path, os.listdir(packages_path)[0])
            info = ConanInfo.loads(load(os.path.join(package_path, CONANINFO)))
            return info

        # Test "A" conaninfo, should filter the FAKE_LIB
        client.save({"conanfile.py": reuse})
        client.run("install . --build missing -e LIB_A:VAR3=override "
                   "-e GLOBAL=99 -e FAKE_LIB:VAR1=-90 -e LIB_B:VAR2=222 "
                   "-e LIB_B2:NEWVAR=VALUE -e VAR3=[newappend]")

        info = load_conaninfo("A")
        self.assertEquals(info.env_values.env_dicts("LIB_A"),
                          ({"VAR3": "override", "GLOBAL": "99"}, {}))
        self.assertEquals(info.env_values.env_dicts(""),
                          ({'GLOBAL': '99'}, {'VAR3': ['newappend']}))

        info = load_conaninfo("B")
        self.assertEquals(info.env_values.env_dicts("LIB_A"), ({'GLOBAL': '99', 'VAR3': "override"},
                                                               {}))

        self.assertEquals(info.env_values.env_dicts("LIB_B"), ({'GLOBAL': '99', "VAR2": "222"},
                                                               {'VAR3': ['newappend']}))

        info = load_conaninfo("B2")
        self.assertEquals(info.env_values.env_dicts("LIB_A"), ({'GLOBAL': '99', 'VAR3': 'override'},
                                                               {}))

        self.assertEquals(info.env_values.env_dicts("LIB_B2"), ({'GLOBAL': '99', 'NEWVAR': "VALUE"},
                                                                {'VAR3': ['newappend']}))

        info = load_conaninfo("C")
        self.assertEquals(info.env_values.env_dicts("LIB_B2"), ({'GLOBAL': '99', 'NEWVAR': "VALUE"},
                                                                {'VAR3': ['newappend']}))
        self.assertEquals(info.env_values.env_dicts("LIB_C"), ({'GLOBAL': '99'},
                                                               {'VAR3': ['newappend']}))

        # Now check the info for the project
        info = ConanInfo.loads(load(os.path.join(client.current_folder, CONANINFO)))
        self.assertEquals(info.env_values.env_dicts("PROJECT"), ({'GLOBAL': '99'},
                                                                 {'VAR3': ['newappend']}))

        _, _, buildinfo = TXTGenerator.loads(load(os.path.join(client.current_folder, BUILD_INFO)))
        self.assertEquals(buildinfo["LIB_A"].VAR1, ["900"])

    def _export(self, client, name, requires, env_vars, env_vars_append=None):
            hello_file = """
import os
from conans import ConanFile

class HelloLib%sConan(ConanFile):
    name = "LIB_%s"
    version = "1.0"
""" % (name, name)

            if requires:
                hello_file += "\n    requires="
                hello_file += ", ".join('"LIB_%s/1.0@lasote/stable"' % require for require in requires)

            hello_file += """
    def package_info(self):
        pass
"""
            if env_vars:
                hello_file += """
        %s
""" % "\n        ".join(["self.env_info.%s = '%s'" % (name, value)
                         for name, value in env_vars.items()])

            if env_vars_append:
                hello_file += """
        %s
""" % "\n        ".join(["self.env_info.%s.append('%s')" % (name, value)
                         for name, value in env_vars_append.items()])

            hello_file += """
    def build(self):
        self.output.info("Building %s, VAR1:%s*" % (self.name, os.environ.get("VAR1", None)))
        self.output.info("Building %s, VAR2:%s*" % (self.name, os.environ.get("VAR2", None)))
        self.output.info("Building %s, VAR3:%s*" % (self.name, os.environ.get("VAR3", None)))

"""
            client.save({"conanfile.py": hello_file}, clean_first=True)
            client.run("export . lasote/stable")


reuse = '''
import os
from conans import ConanFile

class Hello2Conan(ConanFile):
    requires="LIB_C/1.0@lasote/stable"

    def build(self):
        self.output.info("VAR1=>%s*" % os.environ.get("VAR1"))
        self.output.info("VAR2=>%s*" % os.environ.get("VAR2"))
        self.output.info("VAR3=>%s*" % os.environ.get("VAR3"))
'''
