import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANFILE_TXT
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


class TestPackageInfo(unittest.TestCase):

    def package_info_called_in_local_cache_test(self):
        client = TestClient()
        conanfile_tmp = '''
from conans import ConanFile
import os

class HelloConan(ConanFile):
    name = "%s"
    version = "1.0"
    build_policy = "missing"
    options = {"switch": ["1",  "0"]}
    default_options = "switch=0"
    %s
    
    def build(self):
        self.output.warn("Env var MYVAR={0}.".format(os.getenv("MYVAR", "")))

    def package_info(self):
        if self.options.switch == "0": 
            self.env_info.MYVAR = "foo"
        else:
            self.env_info.MYVAR = "bar"

'''
        for index in range(4):
            requires = "requires = 'Lib%s/1.0@conan/stable'" % index if index > 0 else ""
            conanfile = conanfile_tmp % ("Lib%s" % (index + 1), requires)
            client.save({CONANFILE: conanfile}, clean_first=True)
            client.run("create . conan/stable")

        txt = "[requires]\nLib4/1.0@conan/stable"
        client.save({CONANFILE_TXT: txt}, clean_first=True)
        client.run("install . -o *:switch=1")
        self.assertIn("Lib1/1.0@conan/stable: WARN: Env var MYVAR=.", client.out)
        self.assertIn("Lib2/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)
        self.assertIn("Lib3/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)
        self.assertIn("Lib4/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)

        client.run("install . -o *:switch=0 --build Lib3")
        self.assertIn("Lib3/1.0@conan/stable: WARN: Env var MYVAR=foo", client.out)

    def deps_cpp_info_test(self):
        """
        Check that deps_cpp_info information can be modified. This should be fixed
        """
        conanfile_dep = textwrap.dedent("""
            from conans import ConanFile

            class Conan(ConanFile):
                name = "dep"
                version = "1.0"

                def package_info(self):
                    self.cpp_info.filter_empty = False
                    self.cpp_info.includedirs.append("my_include")
                    self.cpp_info.defines.append("SOMETHING")
                    self.cpp_info.libs = ["my_lib"]
            """)

        conanfile_direct_dep = textwrap.dedent("""
            from conans import ConanFile

            class Conan(ConanFile):
                name = "direct_dep"
                version = "1.0"
                requires = "dep/1.0@user/channel"

                def build(self):
                    self.output.info("%s" % self.deps_cpp_info.includedirs)
                    self.output.info("%s" % self.deps_cpp_info.defines)
                    self.output.info("%s" % self.deps_cpp_info.libs)
                    self.deps_cpp_info["dep"].defines = ["ELSE"]
                    self.deps_cpp_info["dep"].includedirs = ["other_include"]
                    self.deps_cpp_info["dep"].libs.append("other_lib")
            """)

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                requires = "direct_dep/1.0@user/channel"

                def build(self):
                    self.output.info("%s" % self.deps_cpp_info.includedirs)
                    self.output.info("%s" % self.deps_cpp_info.defines)
                    self.output.info("%s" % self.deps_cpp_info.libs)
            """)

        client = TestClient()
        client.save({"conanfile_dep.py": conanfile_dep,
                     "conanfile_direct_dep.py": conanfile_direct_dep,
                     "conanfile.py": conanfile})
        client.run("export conanfile_dep.py user/channel")
        client.run("export conanfile_direct_dep.py user/channel")
        client.run("create conanfile.py user/channel --build missing")
        dep_pref = PackageReference(ConanFileReference("dep", "1.0", "user", "channel"),
                                    NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package_layout(dep_pref.ref).package(dep_pref)
        expected_includes = [os.path.join(package_folder, "include"),
                             os.path.join(package_folder, "my_include")]
        self.assertIn("direct_dep/1.0@user/channel: %s" % expected_includes, client.out)
        self.assertIn("direct_dep/1.0@user/channel: %s" % ["SOMETHING"], client.out)
        self.assertIn("direct_dep/1.0@user/channel: %s" % ["my_lib"], client.out)
        expected_includes.append(os.path.join(package_folder, "other_include"))
        self.assertNotIn("consumer/1.0@user/channel: %s"
                         % os.path.join(package_folder, "other_include"), client.out)  # OK
        self.assertIn("consumer/1.0@user/channel: %s" % ["ELSE"], client.out)  # FIXME
        self.assertIn("consumer/1.0@user/channel: %s" % ["my_lib", "other_lib"], client.out)  # FIXME
