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
        # FIXME: Now this is not raising
        # client.run("create . name/1.0@us/ch", assert_error=True)
        # self.assertIn("Setting first level libs is not supported when Components are already in use",
        #               client.out)

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
                self.output.info("GLOBAL Include paths: %s" % self.deps_cpp_info.include_paths)
                self.output.info("GLOBAL Library paths: %s" % self.deps_cpp_info.lib_paths)
                self.output.info("GLOBAL Binary paths: %s" % self.deps_cpp_info.bin_paths)
                self.output.info("GLOBAL Libs: %s" % self.deps_cpp_info.libs)
                self.output.info("GLOBAL Exes: %s" % self.deps_cpp_info.exes)
                self.output.info("GLOBAL System deps: %s" % self.deps_cpp_info.system_deps)
                # Deps values
                for dep_key, dep_value in self.deps_cpp_info.dependencies:
                    self.output.info("DEPS name: %s" % dep_value.name)
                    self.output.info("DEPS Include paths: %s" % dep_value.include_paths)
                    self.output.info("DEPS Library paths: %s" % dep_value.lib_paths)
                    self.output.info("DEPS Binary paths: %s" % dep_value.bin_paths)
                    self.output.info("DEPS Libs: %s" % dep_value.libs)
                    self.output.info("DEPS Exes: %s" % dep_value.exes)
                    self.output.info("DEPS System deps: %s" % dep_value.system_deps)
                # Components values
                for dep_key, dep_value in self.deps_cpp_info.dependencies:
                    for comp_name, comp_value in dep_value.components.items():
                        self.output.info("COMP %s Include paths: %s" % (comp_name,
                        comp_value.include_paths))
                        self.output.info("COMP %s name: %s" % (comp_name, comp_value.name))
                        self.output.info("COMP %s Library paths: %s" % (comp_name, comp_value.lib_paths))
                        self.output.info("COMP %s Binary paths: %s" % (comp_name, comp_value.bin_paths))
                        self.output.info("COMP %s Lib: %s" % (comp_name, comp_value.lib))
                        self.output.info("COMP %s Exe: %s" % (comp_name, comp_value.exe))
                        self.output.info("COMP %s Deps: %s" % (comp_name, comp_value.deps))
                        self.output.info("COMP %s System deps: %s" % (comp_name, comp_value.system_deps))
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

        expected_comp_starlight_include_paths = [os.path.join(package_folder, "galaxy", "starlight")]
        expected_comp_planet_include_paths = [os.path.join(package_folder, "galaxy", "planet")]
        expected_comp_launcher_include_paths = []
        expected_comp_iss_include_paths = [os.path.join(package_folder, "galaxy", "iss")]
        expected_comp_starlight_library_paths = [os.path.join(package_folder, "lib")]
        expected_comp_launcher_library_paths = [os.path.join(package_folder, "lib")]
        expected_comp_planet_library_paths = [os.path.join(package_folder, "lib")]
        expected_comp_iss_library_paths = [os.path.join(package_folder, "iss_libs")]
        expected_comp_starlight_binary_paths = [os.path.join(package_folder, "bin")]
        expected_comp_launcher_binary_paths = [os.path.join(package_folder, "bin")]
        expected_comp_planet_binary_paths = [os.path.join(package_folder, "bin")]
        expected_comp_iss_binary_paths = [os.path.join(package_folder, "bin")]
        expected_comp_starlight_lib = "libstarlight"
        expected_comp_planet_lib = "libplanet"
        expected_comp_launcher_lib = None
        expected_comp_iss_lib = "libiss"
        expected_comp_starlight_system_deps = []
        expected_comp_planet_system_deps = []
        expected_comp_launcher_system_deps = ["ground"]
        expected_comp_iss_system_deps = ["solar", "magnetism"]
        expected_comp_starlight_exe = ""
        expected_comp_planet_exe = ""
        expected_comp_launcher_exe = "exelauncher"
        expected_comp_iss_exe = ""

        expected_global_include_paths = expected_comp_iss_include_paths + \
            expected_comp_planet_include_paths + expected_comp_starlight_include_paths
        expected_global_library_paths = expected_comp_iss_library_paths + \
            expected_comp_starlight_library_paths
        expected_global_binary_paths = expected_comp_starlight_binary_paths
        expected_global_libs = [expected_comp_iss_lib]
        expected_global_libs.extend(expected_comp_iss_system_deps)
        expected_global_libs.extend(expected_comp_launcher_system_deps)
        expected_global_libs.append(expected_comp_planet_lib)
        expected_global_libs.extend(expected_comp_planet_system_deps)
        expected_global_libs.append(expected_comp_starlight_lib)
        expected_global_libs.extend(expected_comp_starlight_system_deps)
        expected_global_exes = [expected_comp_launcher_exe]
        expected_global_system_deps = expected_comp_iss_system_deps + \
            expected_comp_launcher_system_deps

        self.assertIn("GLOBAL Include paths: %s" % expected_global_include_paths, client.out)
        self.assertIn("GLOBAL Library paths: %s" % expected_global_library_paths, client.out)
        self.assertIn("GLOBAL Binary paths: %s" % expected_global_binary_paths, client.out)
        self.assertIn("GLOBAL Libs: %s" % expected_global_libs, client.out)
        self.assertIn("GLOBAL Exes: %s" % expected_global_exes, client.out)
        self.assertIn("GLOBAL System deps: %s" % expected_global_system_deps, client.out)

        self.assertIn("DEPS name: Galaxy", client.out)
        self.assertIn("DEPS Include paths: %s" % expected_global_include_paths, client.out)
        self.assertIn("DEPS Library paths: %s" % expected_global_library_paths, client.out)
        self.assertIn("DEPS Binary paths: %s" % expected_global_binary_paths, client.out)
        self.assertIn("DEPS Libs: %s" % expected_global_libs, client.out)
        self.assertIn("DEPS Exes: %s" % expected_global_exes, client.out)
        self.assertIn("DEPS System deps: %s" % expected_global_system_deps, client.out)

        self.assertIn("COMP Starlight name: Starlight",client.out)
        self.assertIn("COMP Planet name: Planet", client.out)
        self.assertIn("COMP Launcher name: Launcher", client.out)
        self.assertIn("COMP ISS name: ISS", client.out)
        self.assertIn("COMP Starlight Include paths: %s" % expected_comp_starlight_include_paths,
                      client.out)
        self.assertIn("COMP Planet Include paths: %s" % expected_comp_planet_include_paths,
                      client.out)
        self.assertIn("COMP Launcher Include paths: %s" % expected_comp_launcher_include_paths,
                      client.out)
        self.assertIn("COMP ISS Include paths: %s" % expected_comp_iss_include_paths, client.out)
        self.assertIn("COMP Starlight Library paths: %s" % expected_comp_starlight_library_paths,
                      client.out)
        self.assertIn("COMP Planet Library paths: %s" % expected_comp_planet_library_paths,
                      client.out)
        self.assertIn("COMP Launcher Library paths: %s" % expected_comp_launcher_library_paths,
                      client.out)
        self.assertIn("COMP ISS Library paths: %s" % expected_comp_iss_library_paths, client.out)
        self.assertIn("COMP Starlight Binary paths: %s" % expected_comp_iss_binary_paths, client.out)
        self.assertIn("COMP Planet Binary paths: %s" % expected_comp_planet_binary_paths, client.out)
        self.assertIn("COMP Launcher Binary paths: %s" % expected_comp_launcher_binary_paths,
                      client.out)
        self.assertIn("COMP ISS Binary paths: %s" % expected_comp_iss_binary_paths, client.out)
        self.assertIn("COMP Starlight Lib: %s" % expected_comp_starlight_lib, client.out)
        self.assertIn("COMP Planet Lib: %s" % expected_comp_planet_lib, client.out)
        self.assertIn("COMP Launcher Lib: %s" % expected_comp_launcher_lib, client.out)
        self.assertIn("COMP ISS Lib: %s" % expected_comp_iss_lib, client.out)
        self.assertIn("COMP Starlight Exe: %s" % expected_comp_starlight_exe, client.out)
        self.assertIn("COMP Planet Exe: %s" % expected_comp_planet_exe, client.out)
        self.assertIn("COMP Launcher Exe: %s" % expected_comp_launcher_exe, client.out)
        self.assertIn("COMP ISS Exe: %s" % expected_comp_iss_exe, client.out)
        self.assertIn("COMP Starlight System deps: %s" % expected_comp_starlight_system_deps,
                      client.out)
        self.assertIn("COMP Planet System deps: %s" % expected_comp_planet_system_deps, client.out)
        self.assertIn("COMP Launcher System deps: %s" % expected_comp_launcher_system_deps,
                      client.out)
        self.assertIn("COMP ISS System deps: %s" % expected_comp_iss_system_deps, client.out)

    def package_info_diaomond_order_consumer_test(self):
        """
        Check that the value order in deps_cpp_info is the same one when those are recovered from
        conanbuildinfo.txt (consumer case)
        """
        dep = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Conanfile(ConanFile):
                {requires}

                def build(self):
                    self.output.info("%s's deps: %s" % (self.name,
                                                        ", ".join(self.deps_cpp_info.libs)))

                def package_info(self):
                    self.cpp_info.libs = [self.name]
        """)
        client = TestClient()
        client.save({"conanfile.py": dep.format(requires="")})
        client.run("create . zero/1.0@us/ch")
        client.save({"conanfile.py": dep.format(requires="requires = 'zero/1.0@us/ch'")})
        client.run("create . one/1.0@us/ch")
        client.save({"conanfile.py": dep.format(requires="requires = 'zero/1.0@us/ch'")})
        client.run("create . two/1.0@us/ch")
        client.save({
            "conanfile.py": dep.format(requires="requires = 'one/1.0@us/ch', 'two/1.0@us/ch'")})
        client.run("create . three/1.0@us/ch")
        client.save({"conanfile.py": dep.format(requires="requires = 'three/1.0@us/ch'")})
        client.run("create . four/1.0@us/ch")
        self.assertIn("four/1.0@us/ch: four's deps: %s" % ", ".join(["three", "one", "two", "zero"]),
                      client.out)
        client.run("install .")
        client.run("build .")
        self.assertIn("conanfile.py: None's deps: %s" % ", ".join(["three", "one", "two", "zero"]),
                      client.out)
