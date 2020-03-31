import textwrap
import unittest

from conans.errors import ConanException
from conans.paths import CONANFILE, CONANFILE_TXT
from conans.test.utils.tools import TestClient


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

    def package_info_name_test(self):
        dep = textwrap.dedent("""
            from conans import ConanFile

            class Dep(ConanFile):

                def package_info(self):
                    self.cpp_info.name = "MyCustomGreatName"
                """)
        intermediate = textwrap.dedent("""
            from conans import ConanFile

            class Intermediate(ConanFile):
                requires = "dep/1.0@us/ch"
                """)
        consumer = textwrap.dedent("""
            from conans import ConanFile

            class Consumer(ConanFile):
                requires = "intermediate/1.0@us/ch"

                def build(self):
                    for dep_key, dep_value in self.deps_cpp_info.dependencies:
                        self.output.info("%s name: %s" % (dep_key, dep_value.name))
                """)

        client = TestClient()
        client.save({"conanfile_dep.py": dep,
                     "conanfile_intermediate.py": intermediate,
                     "conanfile_consumer.py": consumer})
        client.run("create conanfile_dep.py dep/1.0@us/ch")
        client.run("create conanfile_intermediate.py intermediate/1.0@us/ch")
        client.run("create conanfile_consumer.py consumer/1.0@us/ch")
        self.assertIn("intermediate name: intermediate", client.out)
        self.assertIn("dep name: MyCustomGreatName", client.out)

    def package_info_system_libs_test(self):
        dep = textwrap.dedent("""
            from conans import ConanFile

            class Dep(ConanFile):

                def package_info(self):
                    self.cpp_info.system_libs = ["sysdep1"]
                """)
        intermediate = textwrap.dedent("""
            from conans import ConanFile

            class Intermediate(ConanFile):
                requires = "dep/1.0@us/ch"

                def package_info(self):
                    self.cpp_info.system_libs = ["sysdep2", "sysdep3"]
                """)
        consumer = textwrap.dedent("""
            from conans import ConanFile

            class Consumer(ConanFile):
                requires = "intermediate/1.0@us/ch"

                def build(self):
                    self.output.info("System deps: %s" % self.deps_cpp_info.system_libs)
                    for dep_key, dep_value in self.deps_cpp_info.dependencies:
                        self.output.info("%s system deps: %s" % (dep_key, dep_value.system_libs))
                """)

        client = TestClient()
        client.save({"conanfile_dep.py": dep,
                     "conanfile_intermediate.py": intermediate,
                     "conanfile_consumer.py": consumer})
        client.run("create conanfile_dep.py dep/1.0@us/ch")
        client.run("create conanfile_intermediate.py intermediate/1.0@us/ch")
        client.run("create conanfile_consumer.py consumer/1.0@us/ch")
        dep_system_libs = ["sysdep1"]
        intermediate_system_libs = ["sysdep2", "sysdep3"]
        merged_system_libs = intermediate_system_libs + dep_system_libs
        self.assertIn("System deps: %s" % merged_system_libs, client.out)
        self.assertIn("intermediate system deps: %s" % intermediate_system_libs, client.out)
        self.assertIn("dep system deps: %s" % dep_system_libs, client.out)

    def package_info_components_test(self):
        dep = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Dep(ConanFile):

                def package_info(self):
                    self.cpp_info.components["dep1"].libs.append("libdep1")
                    self.cpp_info.components["dep1"].defines.append("definedep1")
                    self.cpp_info.components["dep2"].libs.append("libdep2")
                    os.mkdir(os.path.join(self.package_folder, "include"))
                    os.mkdir(os.path.join(self.package_folder, "includedep2"))
                    self.cpp_info.components["dep2"].includedirs.append("includedep2")
                """)
        intermediate = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Intermediate(ConanFile):
                requires = "dep/1.0@us/ch"

                def package_info(self):
                    self.cpp_info.components["int1"].libs.append("libint1")
                    self.cpp_info.components["int1"].defines.append("defint1")
                    os.mkdir(os.path.join(self.package_folder, "include"))
                    os.mkdir(os.path.join(self.package_folder, "includeint1"))
                    self.cpp_info.components["int1"].includedirs.append("includeint1")
                    self.cpp_info.components["int2"].libs.append("libint2")
                    self.cpp_info.components["int2"].defines.append("defint2")
                    os.mkdir(os.path.join(self.package_folder, "includeint2"))
                    self.cpp_info.components["int2"].includedirs.append("includeint2")
                """)
        consumer = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Consumer(ConanFile):
                requires = "intermediate/1.0@us/ch"

                def build(self):
                    self.output.info("deps_cpp_info.libs: %s" % self.deps_cpp_info.libs)
                    self.output.info("deps_cpp_info.defines: %s" % self.deps_cpp_info.defines)
                    self.output.info("deps_cpp_info.include_paths: %s" %
                        [os.path.basename(value) for value in self.deps_cpp_info.include_paths])
                    for dep_key, dep_value in self.deps_cpp_info.dependencies:
                        self.output.info("%s.libs: %s" % (dep_key, dep_value.libs))
                        self.output.info("%s.defines: %s" % (dep_key, dep_value.defines))
                        self.output.info("%s.include_paths: %s" % (dep_key,
                                         [os.path.basename(value) for value in
                                         dep_value.include_paths]))
                """)

        client = TestClient()
        client.save({"conanfile_dep.py": dep,
                     "conanfile_intermediate.py": intermediate,
                     "conanfile_consumer.py": consumer})
        client.run("export conanfile_dep.py dep/1.0@us/ch")
        client.run("export conanfile_intermediate.py intermediate/1.0@us/ch")
        client.run("create conanfile_consumer.py consumer/1.0@us/ch --build missing")

        self.assertIn("deps_cpp_info.libs: ['libint1', 'libint2', 'libdep1', 'libdep2']", client.out)
        self.assertIn("deps_cpp_info.defines: ['definedep1', 'defint1', 'defint2']", client.out)
        self.assertIn("deps_cpp_info.include_paths: ['include', 'includeint1', 'includeint2', "
                      "'include', 'includedep2']", client.out)

        self.assertIn("intermediate.libs: ['libint1', 'libint2']",
                      client.out)
        self.assertIn("intermediate.defines: ['defint1', 'defint2']",
                      client.out)
        self.assertIn("intermediate.include_paths: ['include', 'includeint1', 'includeint2']",
                      client.out)

        self.assertIn("dep.libs: ['libdep1', 'libdep2']", client.out)
        self.assertIn("dep.defines: ['definedep1']", client.out)
        self.assertIn("dep.include_paths: ['include', 'includedep2']", client.out)

    def package_info_raise_components_test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Intermediate(ConanFile):

                def package_info(self):
                    self.cpp_info.defines.append("defint")
                    self.cpp_info.components["int1"].libs.append("libint1")
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py dep/1.0@us/ch", assert_error=True)
        self.assertIn("dep/1.0@us/ch package_info(): self.cpp_info.components cannot be used "
                      "with self.cpp_info global values at the same time", client.out)

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Intermediate(ConanFile):

                def package_info(self):
                    self.cpp_info.release.defines.append("defint")
                    self.cpp_info.components["int1"].libs.append("libint1")
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py dep/1.0@us/ch", assert_error=True)
        self.assertIn("dep/1.0@us/ch package_info(): self.cpp_info.components cannot be used "
                      "with self.cpp_info configs (release/debug/...) at the same time", client.out)
