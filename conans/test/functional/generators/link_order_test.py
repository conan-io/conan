import os
import platform
import textwrap
import unittest

from jinja2 import Template
from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


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
            requires = {% for req in requires %}"{{ req }}"{% if not loop.last %}, {% endif %}{% endfor %}
            {% endif %}
            
            def build(self):
                with open("lib" + self.name + ".a", "w+") as f:
                    f.write("fake library content")
                {% for it in libs_extra %}
                with open("lib{{ it }}.a", "w+") as f:
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

                {% if system_libs %}self.cpp_info.system_libs = [{% for it in system_libs %}"{{ it }}"{% if not loop.last %}, {% endif %}{% endfor %}]{% endif %}
    """))

    main_cpp = textwrap.dedent("""
        int main() {return 0;}
    """)

    _expected_link_order = ['liblibD.a', 'libD2.a', 'liblibB.a', 'libB2.a', 'liblibC.a', 'libC2.a',
                            'liblibA.a', 'libA2.a', 'm', 'pthread']

    @classmethod
    def setUpClass(cls):
        libA_ref = ConanFileReference.loads("libA/version")
        libB_ref = ConanFileReference.loads("libB/version")
        libC_ref = ConanFileReference.loads("libC/version")
        libD_ref = ConanFileReference.loads("libD/version")

        t = TestClient(path_with_spaces=False)
        cls._cache_folder = t.cache_folder
        t.save({
            'libA/conanfile.py': cls.conanfile.render(ref=libA_ref,
                                                      libs_extra=["A2"], libs_system=["m"],
                                                      system_libs=["pthread"]),
            'libB/conanfile.py': cls.conanfile.render(ref=libB_ref,
                                                      requires=[libA_ref],
                                                      libs_extra=["B2"], libs_system=["m"],
                                                      system_libs=["pthread"]),
            'libC/conanfile.py': cls.conanfile.render(ref=libC_ref,
                                                      requires=[libA_ref],
                                                      libs_extra=["C2"], libs_system=["m"],
                                                      system_libs=["pthread"]),
            'libD/conanfile.py': cls.conanfile.render(ref=libD_ref,
                                                      requires=[libB_ref, libC_ref],
                                                      libs_extra=["D2"], libs_system=["m"],
                                                      system_libs=["pthread"]),
        })

        # Create all of them
        t.run("create libA")
        t.run("create libB")
        t.run("create libC")
        t.run("create libD")

    @staticmethod
    def _get_link_order_from_cmake(content):
        libs = []
        for it in content.splitlines():
            if 'main.cpp.o  -o example' in it:
                _, links = it.split("main.cpp.o  -o example")
                for it_lib in links.split():
                    if it_lib.startswith("-l"):
                        libs.append(it_lib[2:])
                    else:
                        _, libname = it_lib.rsplit('/', 1)
                        libs.append(libname)
        return libs

    @staticmethod
    def _get_link_order_from_xcode(content):
        libs = []
        for line in content.splitlines():
            if 'OTHER_LDFLAGS = " -Wl,-search_paths_first -Wl,-headerpad_max_install_names' in line.strip():
                _, links = line.split('OTHER_LDFLAGS = " -Wl,-search_paths_first -Wl,-headerpad_max_install_names')
                if links.strip() == '";':
                    continue
                for it_lib in links.strip().split():
                    if it_lib.startswith("-l"):
                        libs.append(it_lib[2:].strip('";'))
                    else:
                        _, libname = it_lib.rsplit('/', 1)
                        libs.append(libname.strip('";'))
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
            t.run_command("cmake --build .")
            # Get the actual link order from the CMake call
            libs = self._get_link_order_from_xcode(t.load(os.path.join('executable.xcodeproj', 'project.pbxproj')))
        else:
            t.run_command("cmake . {} -DCMAKE_VERBOSE_MAKEFILE:BOOL=True"
                          " -DCMAKE_BUILD_TYPE=Release".format(extra_cmake))
            t.run_command("cmake --build .")
            # Get the actual link order from the CMake call
            libs = self._get_link_order_from_cmake(str(t.out))
        return libs

    @parameterized.expand([(None,), ("Xcode",)])
    def test_cmake_find_package_multi(self, generator):
        if generator == "Xcode" and platform.system() != "Darwin":
            self.skipTest("Xcode is needed")

        t = self._create_find_package_project(multi=True)
        libs = self._run_and_get_lib_order(t, generator, find_package_config=True)
        self.assertListEqual(self._expected_link_order, libs)

    @parameterized.expand([(None,), ("Xcode",)])
    def test_cmake_find_package(self, generator):
        if generator == "Xcode" and platform.system() != "Darwin":
            self.skipTest("Xcode is needed")

        t = self._create_find_package_project(multi=False)
        libs = self._run_and_get_lib_order(t, generator)
        self.assertListEqual(self._expected_link_order, libs)

    @parameterized.expand([(None,), ("Xcode",)])
    def test_cmake(self, generator):
        if generator == "Xcode" and platform.system() != "Darwin":
            self.skipTest("Xcode is needed")

        t = self._create_cmake_project(multi=False)
        libs = self._run_and_get_lib_order(t, generator)
        self.assertListEqual(self._expected_link_order, libs)

    @parameterized.expand([(None,), ("Xcode",)])
    def test_cmake_multi(self, generator):
        if generator == "Xcode" and platform.system() != "Darwin":
            self.skipTest("Xcode is needed")

        t = self._create_cmake_project(multi=True)
        libs = self._run_and_get_lib_order(t, generator)
        self.assertListEqual(self._expected_link_order, libs)
