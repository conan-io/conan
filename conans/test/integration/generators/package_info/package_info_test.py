import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANFILE_TXT
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient


class TestPackageInfo(unittest.TestCase):

    def test_package_info_called_in_local_cache(self):
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

    def test_package_info_name(self):
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
                        self.output.info("%s name: %s" % (dep_key, dep_value.get_name('txt')))
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

    def test_package_info_system_libs(self):
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
                    self.output.info("System deps: %s" % list(self.deps_cpp_info.system_libs))
                    for dep_key, dep_value in self.deps_cpp_info.dependencies:
                        self.output.info("%s system deps: %s" % (dep_key, list(dep_value.system_libs)))
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

    def test_package_info_components(self):
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
                    self.cpp_info.components["int1"].requires = ["dep::dep"]  # To avoid exception
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
                    self.output.info("deps_cpp_info.libs: %s" % list(self.deps_cpp_info.libs))
                    self.output.info("deps_cpp_info.defines: %s" % list(self.deps_cpp_info.defines))
                    self.output.info("deps_cpp_info.include_paths: %s" %
                        [os.path.basename(value) for value in self.deps_cpp_info.include_paths])
                    for dep_key, dep_value in self.deps_cpp_info.dependencies:
                        self.output.info("%s.libs: %s" % (dep_key, list(dep_value.libs)))
                        self.output.info("%s.defines: %s" % (dep_key, list(dep_value.defines)))
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

    def test_package_info_raise_components(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MyConan(ConanFile):

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

            class MyConan(ConanFile):

                def package_info(self):
                    self.cpp_info.release.defines.append("defint")
                    self.cpp_info.components["int1"].libs.append("libint1")
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py dep/1.0@us/ch", assert_error=True)
        self.assertIn("dep/1.0@us/ch package_info(): self.cpp_info.components cannot be used "
                      "with self.cpp_info configs (release/debug/...) at the same time", client.out)

        conanfile = textwrap.dedent("""
                    from conans import ConanFile

                    class MyConan(ConanFile):

                        def package_info(self):
                            self.cpp_info.components["dep"].libs.append("libint1")
                """)
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py dep/1.0@us/ch", assert_error=True)
        self.assertIn("dep/1.0@us/ch package_info(): Component name cannot be the same as the "
                      "package name: 'dep'", client.out)

    def test_package_info_components_complete(self):
        dep = textwrap.dedent("""
            import os
            from conans import ConanFile
            class Dep(ConanFile):
                exports_sources = "*"
                def package(self):
                    self.copy("*")
                def package_info(self):
                    self.cpp_info.name = "Galaxy"
                    self.cpp_info.components["Starlight"].includedirs = [os.path.join("galaxy", "starlight")]
                    self.cpp_info.components["Starlight"].libs = ["libstarlight"]
                    self.cpp_info.components["Planet"].includedirs = [os.path.join("galaxy", "planet")]
                    self.cpp_info.components["Planet"].libs = ["libplanet"]
                    self.cpp_info.components["Planet"].requires = ["Starlight"]
                    self.cpp_info.components["Launcher"].system_libs = ["ground"]
                    self.cpp_info.components["ISS"].includedirs = [os.path.join("galaxy", "iss")]
                    self.cpp_info.components["ISS"].libs = ["libiss"]
                    self.cpp_info.components["ISS"].libdirs = ["iss_libs"]
                    self.cpp_info.components["ISS"].system_libs = ["solar", "magnetism"]
                    self.cpp_info.components["ISS"].requires = ["Starlight", "Launcher"]
        """)
        consumer = textwrap.dedent("""
        from conans import ConanFile
        class Consumer(ConanFile):
            requires = "dep/1.0@us/ch"
            def build(self):
                # Global values
                self.output.info("GLOBAL Include paths: %s" % list(self.deps_cpp_info.include_paths))
                self.output.info("GLOBAL Library paths: %s" % list(self.deps_cpp_info.lib_paths))
                self.output.info("GLOBAL Binary paths: %s" % list(self.deps_cpp_info.bin_paths))
                self.output.info("GLOBAL Libs: %s" % list(self.deps_cpp_info.libs))
                self.output.info("GLOBAL System libs: %s" % list(self.deps_cpp_info.system_libs))
                # Deps values
                for dep_key, dep_value in self.deps_cpp_info.dependencies:
                    self.output.info("DEPS name: %s" % dep_value.get_name('txt'))
                    self.output.info("DEPS Include paths: %s" % list(dep_value.include_paths))
                    self.output.info("DEPS Library paths: %s" % list(dep_value.lib_paths))
                    self.output.info("DEPS Binary paths: %s" % list(dep_value.bin_paths))
                    self.output.info("DEPS Libs: %s" % list(dep_value.libs))
                    self.output.info("DEPS System libs: %s" % list(dep_value.system_libs))
                # Components values
                for dep_key, dep_value in self.deps_cpp_info.dependencies:
                    for comp_name, comp_value in dep_value.components.items():
                        self.output.info("COMP %s Include paths: %s" % (comp_name,
                            list(comp_value.include_paths)))
                        self.output.info("COMP %s Library paths: %s" % (comp_name, list(comp_value.lib_paths)))
                        self.output.info("COMP %s Binary paths: %s" % (comp_name, list(comp_value.bin_paths)))
                        self.output.info("COMP %s Libs: %s" % (comp_name, list(comp_value.libs)))
                        self.output.info("COMP %s Requires: %s" % (comp_name, list(comp_value.requires)))
                        self.output.info("COMP %s System libs: %s" % (comp_name, list(comp_value.system_libs)))
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

        expected_global_include_paths = expected_comp_planet_include_paths + \
            expected_comp_iss_include_paths + expected_comp_starlight_include_paths
        expected_global_library_paths = expected_comp_starlight_library_paths + \
            expected_comp_iss_library_paths
        expected_global_binary_paths = expected_comp_starlight_binary_paths

        self.assertIn("GLOBAL Include paths: %s" % expected_global_include_paths, client.out)
        self.assertIn("GLOBAL Library paths: %s" % expected_global_library_paths, client.out)
        self.assertIn("GLOBAL Binary paths: %s" % expected_global_binary_paths, client.out)
        self.assertIn("GLOBAL Libs: ['libplanet', 'libiss', 'libstarlight']", client.out)
        self.assertIn("GLOBAL System libs: ['solar', 'magnetism', 'ground']", client.out)

        self.assertIn("DEPS name: Galaxy", client.out)
        self.assertIn("DEPS Include paths: %s" % expected_global_include_paths, client.out)
        self.assertIn("DEPS Library paths: %s" % expected_global_library_paths, client.out)
        self.assertIn("DEPS Binary paths: %s" % expected_global_binary_paths, client.out)
        self.assertIn("DEPS Libs: ['libplanet', 'libiss', 'libstarlight']", client.out)
        self.assertIn("DEPS System libs: ['solar', 'magnetism', 'ground']", client.out)

        self.assertIn("COMP Starlight Include paths: %s" % list(expected_comp_starlight_include_paths),
                      client.out)
        self.assertIn("COMP Planet Include paths: %s" % list(expected_comp_planet_include_paths,),
                      client.out)
        self.assertIn("COMP Launcher Include paths: %s" % list(expected_comp_launcher_include_paths),
                      client.out)
        self.assertIn("COMP ISS Include paths: %s" % list(expected_comp_iss_include_paths), client.out)
        self.assertIn("COMP Starlight Library paths: %s" % list(expected_comp_starlight_library_paths),
                      client.out)
        self.assertIn("COMP Planet Library paths: %s" % list(expected_comp_planet_library_paths),
                      client.out)
        self.assertIn("COMP Launcher Library paths: %s" % list(expected_comp_launcher_library_paths),
                      client.out)
        self.assertIn("COMP ISS Library paths: %s" % list(expected_comp_iss_library_paths), client.out)
        self.assertIn("COMP Starlight Binary paths: %s" % list(expected_comp_iss_binary_paths), client.out)
        self.assertIn("COMP Planet Binary paths: %s" % list(expected_comp_planet_binary_paths), client.out)
        self.assertIn("COMP Launcher Binary paths: %s" % list(expected_comp_launcher_binary_paths),
                      client.out)
        self.assertIn("COMP ISS Binary paths: %s" % list(expected_comp_iss_binary_paths), client.out)
        self.assertIn("COMP Starlight Libs: ['libstarlight']", client.out)
        self.assertIn("COMP Planet Libs: ['libplanet']", client.out)
        self.assertIn("COMP Launcher Libs: []", client.out)
        self.assertIn("COMP ISS Libs: ['libiss']", client.out)
        self.assertIn("COMP Starlight System libs: []", client.out)
        self.assertIn("COMP Planet System libs: []", client.out)
        self.assertIn("COMP Launcher System libs: ['ground']", client.out)
        self.assertIn("COMP ISS System libs: ['solar', 'magnetism']", client.out)
        self.assertIn("COMP Starlight Requires: []", client.out)
        self.assertIn("COMP Launcher Requires: []", client.out)
        self.assertIn("COMP Planet Requires: ['Starlight']", client.out)
        self.assertIn("COMP ISS Requires: ['Starlight', 'Launcher']", client.out)

    def test_package_requires_in_components_requires(self):
        client = TestClient()
        client.save({"conanfile1.py": GenConanfile("dep1", "0.1"),
                     "conanfile2.py": GenConanfile("dep2", "0.1")})
        client.run("create conanfile1.py")
        client.run("create conanfile2.py")

        conanfile = GenConanfile("consumer", "0.1") \
            .with_requirement("dep1/0.1") \
            .with_requirement("dep2/0.1") \
            .with_package_info(cpp_info={"components": {"kk": {"requires": []}}},
                               env_info={})
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py", assert_error=True)
        self.assertIn("consumer/0.1 package_info(): Package require 'dep1' not used in "
                      "components requires", client.out)

        conanfile = GenConanfile("consumer", "0.1") \
            .with_requirement("dep1/0.1") \
            .with_requirement("dep2/0.1") \
            .with_package_info(cpp_info={"components": {"kk": {"requires": ["dep1::dep1"]}}},
                               env_info={})
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py", assert_error=True)
        self.assertIn("consumer/0.1 package_info(): Package require 'dep2' not used in components "
                      "requires", client.out)

        conanfile = GenConanfile("consumer", "0.1") \
            .with_requirement("dep1/0.1") \
            .with_requirement("dep2/0.1") \
            .with_package_info(cpp_info={"components": {"kk": {"requires": ["dep1::dep1"]},
                                                        "kkk": {"requires": ["kk"]}}},
                               env_info={})
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py", assert_error=True)
        self.assertIn("consumer/0.1 package_info(): Package require 'dep2' not used in components "
                      "requires", client.out)

        conanfile = GenConanfile("consumer", "0.1") \
            .with_requirement("dep1/0.1") \
            .with_requirement("dep2/0.1") \
            .with_package_info(cpp_info={"components": {"kk": {"requires": []},
                                                        "kkk": {"requires": ["kk"]}}},
                               env_info={})
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py", assert_error=True)
        self.assertIn("consumer/0.1 package_info(): Package require 'dep1' not used in components "
                      "requires", client.out)

        conanfile = GenConanfile("consumer", "0.1") \
            .with_requirement("dep1/0.1") \
            .with_requirement("dep2/0.1") \
            .with_package_info(cpp_info={"components": {"kk": {"requires": ["dep2::comp"]},
                                                        "kkk": {"requires": ["dep3::dep3"]}}},
                               env_info={})
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py", assert_error=True)
        self.assertIn("consumer/0.1 package_info(): Package require 'dep1' not used in components "
                      "requires", client.out)

        conanfile = GenConanfile("consumer", "0.1") \
            .with_requirement("dep2/0.1") \
            .with_package_info(cpp_info={"components": {"kk": {"requires": ["dep2::comp"]},
                                                        "kkk": {"requires": ["dep3::dep3"]}}},
                               env_info={})
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py", assert_error=True)
        self.assertIn("consumer/0.1 package_info(): Package require 'dep3' declared in components "
                      "requires but not defined as a recipe requirement", client.out)

        conanfile = GenConanfile("consumer", "0.1") \
            .with_package_info(cpp_info={"components": {"kk": {"requires": ["dep2::comp"]}}},
                               env_info={})
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py", assert_error=True)
        self.assertIn("consumer/0.1 package_info(): Package require 'dep2' declared in components "
                      "requires but not defined as a recipe requirement", client.out)

        conanfile = GenConanfile("consumer", "0.1") \
            .with_requirement("dep1/0.1") \
            .with_requirement("dep2/0.1") \
            .with_package_info(cpp_info={"components": {"kk": {"requires": ["dep2::comp"]},
                                                        "kkk": {"requires": ["dep1::dep1"]}}},
                               env_info={})
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py")  # Correct usage

    def test_get_name_local_flow(self):
        # https://github.com/conan-io/conan/issues/7854
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Package(ConanFile):
                def package_info(self):
                    self.cpp_info.names["cmake_find_package"] = "GTest"
                    self.cpp_info.filenames["cmake_find_package"] = "GtesT"
                """)
        client.save({"conanfile.py": conanfile})
        client.run("create . gtest/1.0@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Package(ConanFile):
                requires = 'gtest/1.0'

                def build(self):
                    info = self.deps_cpp_info['gtest'].get_name('cmake_find_package')
                    self.output.info("GTEST_INFO: %s" % info)
                    fileinfo = self.deps_cpp_info['gtest'].get_filename('cmake_find_package')
                    self.output.info("GTEST_FILEINFO: %s" % fileinfo)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/1.0@")
        self.assertIn("pkg/1.0: GTEST_INFO: GTest", client.out)
        self.assertIn("pkg/1.0: GTEST_FILEINFO: GtesT", client.out)
        client.run("install . pkg/1.0@")
        client.run("build .")
        self.assertIn("conanfile.py (pkg/1.0): GTEST_INFO: GTest", client.out)
        self.assertIn("conanfile.py (pkg/1.0): GTEST_FILEINFO: GtesT", client.out)

    def test_none_folders(self):
        # https://github.com/conan-io/conan/issues/11856
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class pkgConan(ConanFile):
                def package_info(self):
                    self.cpp_info.resdirs = [None]
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/1.0@")
        assert "Created package revision" in client.out
