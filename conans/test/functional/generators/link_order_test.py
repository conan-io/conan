import os
import platform
import textwrap
import unittest

import pytest
from jinja2 import Template
from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake(version="3.19")
class LinkOrderTest(unittest.TestCase):
    """ Check that the link order of libraries is preserved when using CMake generators
        https://github.com/conan-io/conan/issues/6280
    """

    conanfile = Template(textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "{{ref.name}}"
            version = "{{ref.version}}"

            {% if requires %}
            requires =
                {%- for req in requires -%}
                "{{ req }}"{% if not loop.last %}, {% endif %}
                {%- endfor -%}
            {% endif %}

            def build(self):
                with open("lib" + self.name + ".a", "w+") as f:
                    f.write("fake library content")
                with open(self.name + ".lib", "w+") as f:
                    f.write("fake library content")

                {% for it in libs_extra %}
                with open("lib{{ it }}.a", "w+") as f:
                    f.write("fake library content")
                with open("{{ it }}.lib", "w+") as f:
                    f.write("fake library content")
                {% endfor %}

            def package(self):
                self.copy("*.a", dst="lib")
                self.copy("*.lib", dst="lib")

            def package_info(self):
                # Libraries
                self.cpp_info.libs = ["{{ ref.name }}"]
                {% for it in libs_extra %}
                self.cpp_info.libs.append("{{ it }}")
                {% endfor %}
                {% for it in libs_system %}
                self.cpp_info.libs.append("{{ it }}")
                {% endfor %}

                {% if system_libs %}
                self.cpp_info.system_libs = [
                    {%- for it in system_libs -%}
                    "{{ it }}"{% if not loop.last %}, {% endif %}
                    {%- endfor -%}]
                {% endif %}

                {% if frameworks %}
                self.cpp_info.frameworks.extend([
                    {%- for it in frameworks -%}
                    "{{ it }}"{% if not loop.last %}, {% endif %}
                    {%- endfor -%}])
                {% endif %}
    """))

    conanfile_headeronly = Template(textwrap.dedent("""
        from conans import ConanFile

        class HeaderOnly(ConanFile):
            name = "{{ref.name}}"
            version = "{{ref.version}}"

            {% if requires %}
            requires =
                {%- for req in requires -%}
                "{{ req }}"{% if not loop.last %}, {% endif %}
                {%- endfor -%}
            {% endif %}

            def package_id(self):
                self.info.header_only()

            def package_info(self):
                # It may declare system libraries
                {% for it in libs_system %}
                self.cpp_info.libs.append("{{ it }}")
                {% endfor %}

                {% if system_libs %}
                self.cpp_info.system_libs = [
                    {%- for it in system_libs -%}
                    "{{ it }}"{% if not loop.last %}, {% endif %}
                    {%- endfor -%}]
                {% endif %}

                {% if frameworks %}
                self.cpp_info.frameworks.extend([
                    {%- for it in frameworks -%}
                    "{{ it }}"{% if not loop.last %}, {% endif %}
                    {%- endfor -%}])
                {% endif %}
    """))

    main_cpp = textwrap.dedent("""
        int main() {return 0;}
    """)

    @classmethod
    def setUpClass(cls):
        libZ_ref = ConanFileReference.loads("libZ/version")
        libH2_ref = ConanFileReference.loads("header2/version")
        libH_ref = ConanFileReference.loads("header/version")
        libA_ref = ConanFileReference.loads("libA/version")
        libB_ref = ConanFileReference.loads("libB/version")
        libC_ref = ConanFileReference.loads("libC/version")
        libD_ref = ConanFileReference.loads("libD/version")

        t = TestClient(path_with_spaces=False)
        cls._cache_folder = t.cache_folder
        t.save({
            'libZ/conanfile.py': cls.conanfile.render(
                ref=libZ_ref,
                libs_extra=["Z2"],
                libs_system=["system_assumed"],
                system_libs=["system_lib"],
                frameworks=["Carbon"]),
            'libH2/conanfile.py': cls.conanfile_headeronly.render(
                ref=libH2_ref,
                libs_system=["header2_system_assumed"],
                system_libs=["header2_system_lib"],
                frameworks=["Security"]),
            'libH/conanfile.py': cls.conanfile_headeronly.render(
                ref=libH_ref,
                requires=[libH2_ref, libZ_ref],
                libs_system=["header_system_assumed"],
                system_libs=["header_system_lib"],
                frameworks=["CoreAudio"]),
            'libA/conanfile.py': cls.conanfile.render(
                ref=libA_ref,
                requires=[libH_ref],
                libs_extra=["A2"],
                libs_system=["system_assumed"],
                system_libs=["system_lib"],
                frameworks=["Carbon"]),
            'libB/conanfile.py': cls.conanfile.render(
                ref=libB_ref,
                requires=[libA_ref],
                libs_extra=["B2"],
                libs_system=["system_assumed"],
                system_libs=["system_lib"],
                frameworks=["Carbon"]),
            'libC/conanfile.py': cls.conanfile.render(
                ref=libC_ref,
                requires=[libA_ref],
                libs_extra=["C2"],
                libs_system=["system_assumed"],
                system_libs=["system_lib"],
                frameworks=["Carbon"]),
            'libD/conanfile.py': cls.conanfile.render(
                ref=libD_ref,
                requires=[libB_ref, libC_ref],
                libs_extra=["D2"],
                libs_system=["system_assumed"],
                system_libs=["system_lib"],
                frameworks=["Carbon"]),
        })

        # Create all of them
        t.run("create libZ")
        t.run("create libH2")
        t.run("create libH")
        t.run("create libA")
        t.run("create libB")
        t.run("create libC")
        t.run("create libD")

    def _validate_link_order(self, libs):
        # Check that all the libraries are there:
        self.assertEqual(len(libs), 19 if platform.system() == "Darwin" else
                         16 if platform.system() == "Linux" else 26,
                         msg="Unexpected number of libs ({}):"
                             " '{}'".format(len(libs), "', '".join(libs)))
        # - Regular libs
        ext = ".lib" if platform.system() == "Windows" else ".a"
        prefix = "" if platform.system() == "Windows" else "lib"
        expected_libs = {prefix + it + ext for it in ['libD', 'D2', 'libB', 'B2', 'libC', 'C2',
                                                      'libA', 'A2', 'libZ', 'Z2']}
        # - System libs
        ext_system = ".lib" if platform.system() == "Windows" else ""
        expected_libs.update([it + ext_system for it in ['header_system_assumed',
                                                         'header_system_lib',
                                                         'header2_system_assumed',
                                                         'header2_system_lib',
                                                         'system_assumed',
                                                         'system_lib']])
        # - Add MacOS frameworks
        if platform.system() == "Darwin":
            expected_libs.update(['CoreAudio', 'Security', 'Carbon'])
        # - Add Windows libs
        if platform.system() == "Windows":
            expected_libs.update(['kernel32.lib', 'user32.lib', 'gdi32.lib', 'winspool.lib',
                                  'shell32.lib', 'ole32.lib', 'oleaut32.lib', 'uuid.lib',
                                  'comdlg32.lib', 'advapi32.lib'])
        self.assertSetEqual(set(libs), expected_libs)

        # These are the first libraries and order is mandatory
        mandatory_1 = [prefix + it + ext for it in ['libD', 'D2', 'libB', 'B2', 'libC',
                                                    'C2', 'libA', 'A2', ]]
        self.assertListEqual(mandatory_1, libs[:len(mandatory_1)])

        # Then, libZ ones must be before system libraries that are consuming
        self.assertLess(libs.index(prefix + 'libZ' + ext),
                        min(libs.index('system_assumed' + ext_system),
                            libs.index('system_lib' + ext_system)))
        self.assertLess(libs.index(prefix + 'Z2' + ext),
                        min(libs.index('system_assumed' + ext_system),
                            libs.index('system_lib' + ext_system)))
        if platform.system() == "Darwin":
            self.assertLess(libs.index('liblibZ.a'), libs.index('Carbon'))
            self.assertLess(libs.index('libZ2.a'), libs.index('Carbon'))

    @staticmethod
    def _get_link_order_from_cmake(content):
        libs = []
        for it in content.splitlines():
            # This is for Linux and Mac
            # Remove double spaces from output that appear in some platforms
            line = ' '.join(it.split())
            if 'main.cpp.o -o example' in line:
                _, links = line.split("main.cpp.o -o example")
                for it_lib in links.split():
                    if it_lib.startswith("-l"):
                        libs.append(it_lib[2:])
                    elif it_lib == "-framework":
                        continue
                    else:
                        try:
                            _, libname = it_lib.rsplit('/', 1)
                        except ValueError:
                            libname = it_lib
                        finally:
                            libs.append(libname)
                break
            # Windows
            if 'example.exe" /INCREMENTAL:NO /NOLOGO' in it:
                for it_lib in it.split():
                    it_lib = it_lib.strip()
                    if it_lib.endswith(".lib"):
                        try:
                            _, libname = it_lib.rsplit('\\', 1)
                        except ValueError:
                            libname = it_lib
                        finally:
                            libs.append(libname)
                break
        return libs

    @staticmethod
    def _get_link_order_from_xcode(content):
        libs = []
        start_key = 'OTHER_LDFLAGS = (" -Wl,-search_paths_first -Wl,-headerpad_max_install_names",'
        end_key = '");'
        libs_content = content.split(start_key, 1)[1].split(end_key, 1)[0]
        libs_unstripped = libs_content.split(",")
        for lib in libs_unstripped:
            if ".a" in lib:
                libs.append(lib.strip('"').rsplit('/', 1)[1])
            elif "-l" in lib:
                libs.append(lib.strip('"')[2:])
            elif "-framework" in lib:
                libs.append(lib.strip('"')[11:])
        return libs

    def _create_find_package_project(self, multi):
        generator = "cmake_find_package_multi" if multi else "cmake_find_package"
        t = TestClient(cache_folder=self._cache_folder)
        t.save({
            'conanfile.txt': textwrap.dedent("""
                [requires]
                libD/version
                [generators]
                {}
                """.format(generator)),
            'CMakeLists.txt': textwrap.dedent("""
                cmake_minimum_required(VERSION 2.8.12)
                project(executable CXX)

                find_package(libD)
                add_executable(example main.cpp)
                target_link_libraries(example libD::libD)
                """),
            'main.cpp': self.main_cpp
        })

        t.run("install . -s build_type=Release")
        return t

    def _create_cmake_project(self, multi):
        generator = "cmake_multi" if multi else "cmake"
        include_cmake_file = "conanbuildinfo_multi" if multi else "conanbuildinfo"
        t = TestClient(cache_folder=self._cache_folder)
        t.save({
            'conanfile.txt': textwrap.dedent("""
                [requires]
                libD/version
                [generators]
                {}
                """.format(generator)),
            'CMakeLists.txt': textwrap.dedent("""
                cmake_minimum_required(VERSION 2.8.12)
                project(executable CXX)

                include(${{CMAKE_BINARY_DIR}}/{}.cmake)
                conan_basic_setup(TARGETS NO_OUTPUT_DIRS)

                add_executable(example main.cpp)
                target_link_libraries(example CONAN_PKG::libD)
                """.format(include_cmake_file)),
            'main.cpp': self.main_cpp
        })

        t.run("install . -s build_type=Release")
        t.save({"conanbuildinfo_debug.cmake": "# just be there"})
        return t

    def _run_and_get_lib_order(self, t, generator, find_package_config=False):
        extra_cmake = "-DCMAKE_PREFIX_PATH=." if find_package_config else "-DCMAKE_MODULE_PATH=."
        if generator == "Xcode":
            t.run_command("cmake . -G Xcode {} -DCMAKE_VERBOSE_MAKEFILE:BOOL=True"
                          " -DCMAKE_CONFIGURATION_TYPES=Release".format(extra_cmake))
            t.run_command("cmake --build .", assert_error=True)
            # Get the actual link order from the CMake call
            libs = self._get_link_order_from_xcode(t.load(os.path.join('executable.xcodeproj',
                                                                       'project.pbxproj')))
        else:
            t.run_command("cmake . {} -DCMAKE_VERBOSE_MAKEFILE:BOOL=True"
                          " -DCMAKE_BUILD_TYPE=Release".format(extra_cmake))
            extra_build = "--config Release" if platform.system() == "Windows" else ""  # Windows VS
            t.run_command("cmake --build . {}".format(extra_build), assert_error=True)
            # Get the actual link order from the CMake call
            libs = self._get_link_order_from_cmake(str(t.out))
        return libs

    @parameterized.expand([(None,), ("Xcode",)])
    def test_cmake_find_package_multi(self, generator):
        if generator == "Xcode" and platform.system() != "Darwin":
            self.skipTest("Xcode is needed")

        t = self._create_find_package_project(multi=True)
        libs = self._run_and_get_lib_order(t, generator, find_package_config=True)
        self._validate_link_order(libs)

    @parameterized.expand([(None,), ("Xcode",)])
    def test_cmake_find_package(self, generator):
        if generator == "Xcode" and platform.system() != "Darwin":
            self.skipTest("Xcode is needed")

        t = self._create_find_package_project(multi=False)
        libs = self._run_and_get_lib_order(t, generator)
        self._validate_link_order(libs)

    @parameterized.expand([(None,), ("Xcode",)])
    def test_cmake(self, generator):
        if generator == "Xcode" and platform.system() != "Darwin":
            self.skipTest("Xcode is needed")

        t = self._create_cmake_project(multi=False)
        libs = self._run_and_get_lib_order(t, generator)
        self._validate_link_order(libs)

    @parameterized.expand([(None,), ("Xcode",)])
    def test_cmake_multi(self, generator):
        if generator == "Xcode" and platform.system() != "Darwin":
            self.skipTest("Xcode is needed")

        t = self._create_cmake_project(multi=True)
        libs = self._run_and_get_lib_order(t, generator)
        self._validate_link_order(libs)
