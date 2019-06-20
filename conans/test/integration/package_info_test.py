import os
import textwrap
import unittest

import six

from conans.errors import ConanException
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

    def package_info_components_test(self):
        dep = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Dep(ConanFile):
                exports_sources = "*"

                def package(self):
                    self.copy("*")

                def package_info(self):
                    self.cpp_info.name = "Boost"
                    self.cpp_info["Accumulators"].includedirs = [os.path.join("boost", "accumulators")]
                    self.cpp_info["Accumulators"].lib = "libaccumulators"
                    self.cpp_info["Containers"].includedirs = [os.path.join("boost", "containers")]
                    self.cpp_info["Containers"].lib = "libcontainers"
                    self.cpp_info["Containers"].deps = ["Accumulators"]
                    self.cpp_info["SuperContainers"].includedirs = [os.path.join("boost",
                                                                                 "supercontainers")]
                    self.cpp_info["SuperContainers"].lib = "libsupercontainers"
                    self.cpp_info["SuperContainers"].deps = ["Containers"]
        """)
        consumer = textwrap.dedent("""
            from conans import ConanFile

            class Consumer(ConanFile):
                requires = "dep/1.0@us/ch"

                def build(self):
                    acc_includes = self.deps_cpp_info["dep"]["Accumulators"].include_paths
                    con_include = self.deps_cpp_info["dep"]["Containers"].include_paths
                    sup_include = self.deps_cpp_info["dep"]["SuperContainers"].include_paths
                    self.output.info("Name: %s" % self.deps_cpp_info["dep"].name)
                    self.output.info("Accumulators: %s" % acc_includes)
                    self.output.info("Containers: %s" % con_include)
                    self.output.info("SuperContainers: %s" % sup_include)
                    self.output.info("LIBS: %s" % self.deps_cpp_info["dep"].libs)
        """)

        client = TestClient()
        client.save({"conanfile_dep.py": dep, "conanfile_consumer.py": consumer,
                     "boost/boost.h": "",
                     "boost/accumulators/accumulators.h": "",
                     "boost/containers/containers.h": "",
                     "boost/supercontainers/supercontainers.h": ""})
        dep_ref = ConanFileReference("dep", "1.0", "us", "ch")
        dep_pref = PackageReference(dep_ref, NO_SETTINGS_PACKAGE_ID)
        client.run("create conanfile_dep.py dep/1.0@us/ch")
        client.run("create conanfile_consumer.py consumer/1.0@us/ch")
        package_folder = client.cache.package_layout(dep_ref).package(dep_pref)
        accumulators_expected = [os.path.join(package_folder, "boost", "accumulators")]
        containers_expected = [os.path.join(package_folder, "boost", "containers")]
        supercontainers_expected = [os.path.join(package_folder, "boost", "supercontainers")]
        self.assertIn("Name: Boost", client.out)
        self.assertIn("LIBS: ['libaccumulators', 'libcontainers', 'libsupercontainers']", client.out)
        self.assertIn("Accumulators: %s" % accumulators_expected, client.out)
        self.assertIn("Containers: %s" % containers_expected, client.out)
        self.assertIn("SuperContainers: %s" % supercontainers_expected, client.out)

    def package_info_wrong_cpp_info_test(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Dep(ConanFile):

                def package_info(self):
                    self.cpp_info.name = "Boost"
                    self.cpp_info["Accumulators"].includedirs = [os.path.join("boost", "accumulators")]
                    self.cpp_info.libs = ["hello"]
        """)

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . name/1.0@us/ch")  # Does NOT fail on export
        client.run("create . name/1.0@us/ch", assert_error=True)
        self.assertIn("Setting first level libs is not supported when Components are already in use",
                      client.out)

    def package_info_components_complete_test(self):
        dep = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Dep(ConanFile):
                exports_sources = "*"

                def package(self):
                    self.copy("*")

                def package_info(self):
                    self.cpp_info.name = "Galaxy"
                    self.cpp_info["Starlight"].includedirs = [os.path.join("galaxy", "starlight")]
                    self.cpp_info["Starlight"].lib = "libstarlight"

                    self.cpp_info["Planet"].includedirs = [os.path.join("galaxy", "planet")]
                    self.cpp_info["Planet"].lib = "libplanet"
                    self.cpp_info["Planet"].deps = ["Starlight"]

                    self.cpp_info["Launcher"].exe = "exelauncher"
                    self.cpp_info["Launcher"].system_deps = ["ground"]

                    self.cpp_info["ISS"].includedirs = [os.path.join("galaxy", "iss")]
                    self.cpp_info["ISS"].lib = "libiss"
                    self.cpp_info["ISS"].libdirs = ["iss_libs"]
                    self.cpp_info["ISS"].system_deps = ["solar", "magnetism"]
                    self.cpp_info["ISS"].deps = ["Starlight", "Launcher"]
        """)
        consumer = textwrap.dedent("""
        from conans import ConanFile

        class Consumer(ConanFile):
            requires = "dep/1.0@us/ch"

            def build(self):
                # Global values
                self.output.info("GLOBAL Include Paths: %s" % self.deps_cpp_info.include_paths)
                self.output.info("GLOBAL Library Paths: %s" % self.deps_cpp_info.lib_paths)
                self.output.info("GLOBAL Binary Paths: %s" % self.deps_cpp_info.bin_paths)
                self.output.info("GLOBAL Libs: %s" % self.deps_cpp_info.libs)
                self.output.info("GLOBAL Exes: %s" % self.deps_cpp_info.exes)
                # Deps values
                for dep_key, dep_value in self.deps_cpp_info.dependencies:
                    self.output.info("DEPS Include paths: %s" % dep_value.include_paths)
                    self.output.info("DEPS Library paths: %s" % dep_value.lib_paths)
                    self.output.info("DEPS Binary paths: %s" % dep_value.bin_paths)
                    self.output.info("DEPS Libs: %s" % dep_value.libs)
                    self.output.info("DEPS Exes: %s" % dep_value.exes)
                # Components values
                for dep_key, dep_value in self.deps_cpp_info.dependencies:
                    for comp_name, comp_value in dep_value.deps.items():
                        self.output.info("COMP %s Include paths: %s" % (comp_name,
                        comp_value.include_paths))
                        self.output.info("COMP %s Library paths: %s" % (comp_name, comp_value.lib_paths))
                        self.output.info("COMP %s Binary paths: %s" % (comp_name, comp_value.bin_paths))
                        self.output.info("COMP %s Lib: %s" % (comp_name, comp_value.lib))
                        self.output.info("COMP %s Exe: %s" % (comp_name, comp_value.exe))
                        self.output.info("COMP %s Deps: %s" % (comp_name, comp_value.deps))
        """)

        client = TestClient()
        client.save({"conanfile_dep.py": dep, "conanfile_consumer.py": consumer,
                     "galaxy/starlight/starlight.h": "",
                     "lib/libstarlight": "",
                     "galaxy/planet/planet.h": "",
                     "lib/libplanet": "",
                     "galaxy/iss/iss.h": "",
                     "iss_libs/libiss": "",
                     "bin/exelauncher": ""})
        dep_ref = ConanFileReference("dep", "1.0", "us", "ch")
        dep_pref = PackageReference(dep_ref, NO_SETTINGS_PACKAGE_ID)
        client.run("create conanfile_dep.py dep/1.0@us/ch")
        client.run("create conanfile_consumer.py consumer/1.0@us/ch")
        package_folder = client.cache.package_layout(dep_ref).package(dep_pref)

        expected_global_include_paths = [os.path.join(package_folder, "galaxy", "starlight"),
                                         os.path.join(package_folder, "galaxy", "planet"),
                                         os.path.join(package_folder, "galaxy", "iss")]
        expected_global_library_paths = [os.path.join(package_folder, "lib"),
                                         os.path.join(package_folder, "iss_libs")]
        expected_global_binary_paths = [os.path.join(package_folder, "bin")]
        expected_global_libs = ["libstarlight", "ground", "libplanet", "solar", "magnetism", "libiss"]
        expected_global_exes = ["exelauncher"]
        self.assertIn("GLOBAL Include Paths: %s" % expected_global_include_paths, client.out)
        self.assertIn("GLOBAL Library Paths: %s" % expected_global_library_paths, client.out)
        self.assertIn("GLOBAL Binary Paths: %s" % expected_global_binary_paths, client.out)
        self.assertIn("GLOBAL Libs: %s" % expected_global_libs, client.out)
        self.assertIn("GLOBAL Exes: %s" % expected_global_exes, client.out)

        self.assertIn("DEPS Include Paths: {}".format(expected_global_include_paths), client.out)
        self.assertIn("DEPS Library Paths: %s" % expected_global_library_paths, client.out)
        self.assertIn("DEPS Binary Paths: %s" % expected_global_binary_paths, client.out)
        self.assertIn("DEPS Libs: %s" % expected_global_libs, client.out)
        self.assertIn("DEPS Exes: %s" % expected_global_exes, client.out)

        #TODO: Complete the test checking the output of the components
