import os
import platform
import textwrap
import unittest

from jinja2 import Template

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

    @unittest.skipIf(platform.system() != "Darwin", "Xcode is needed")
    def test_xcode_find_package_multi(self):
        t = TestClient(cache_folder=self._cache_folder)
        t.save({
            'conanfile.txt': textwrap.dedent("""
                [requires]
                libD/version
                [generators]
                cmake_find_package_multi
                """),
            'CMakeLists.txt': textwrap.dedent("""
                cmake_minimum_required(VERSION 2.8.12)
                project(executable CXX)

                find_package(libD)
                add_executable(example main.cpp)
                target_link_libraries(example libD::libD)
                """),
            'main.cpp': textwrap.dedent("""
                int main() {return 0;}
                """)
        })

        t.run("install . -s build_type=Release")
        t.run_command("cmake . -G Xcode -DCMAKE_PREFIX_PATH=. -DCMAKE_VERBOSE_MAKEFILE:BOOL=True")
        t.run_command("cmake --build .")

        # Get the actual link order from the CMake call
        libs = []
        for line in t.load(os.path.join('executable.xcodeproj', 'project.pbxproj')).splitlines():
            if 'OTHER_LDFLAGS = " -Wl,-search_paths_first -Wl,-headerpad_max_install_names' in line.strip():
                _, links = line.split('OTHER_LDFLAGS = " -Wl,-search_paths_first -Wl,-headerpad_max_install_names')
                if links == '  ";':
                    continue
                for it_lib in links.strip().split():
                    if it_lib.startswith("-l"):
                        libs.append(it_lib[2:])
                    else:
                        _, libname = it_lib.rsplit('/', 1)
                        libs.append(libname.strip('";'))

        self.assertListEqual(self._expected_link_order, libs)

    def test_cmake_find_package(self):
        t = TestClient(cache_folder=self._cache_folder)
        t.save({
            'conanfile.txt': textwrap.dedent("""
                [requires]
                libD/version
                [generators]
                cmake_find_package
                """),
            'CMakeLists.txt': textwrap.dedent("""
                cmake_minimum_required(VERSION 2.8.12)
                project(executable CXX)

                find_package(libD)
                add_executable(example main.cpp)
                target_link_libraries(example libD::libD)
                """),
            'main.cpp': textwrap.dedent("""
                int main() {return 0;}
                """)
        })

        t.run("install .")
        t.run_command("cmake . -DCMAKE_MODULE_PATH=. -DCMAKE_VERBOSE_MAKEFILE:BOOL=True")
        t.run_command("cmake --build .")

        # Get the actual link order from the CMake call
        libs = []
        for it in str(t.out).splitlines():
            if 'main.cpp.o  -o example' in it:
                _, links = it.split("main.cpp.o  -o example")
                for it_lib in links.split():
                    if it_lib.startswith("-l"):
                        libs.append(it_lib[2:])
                    else:
                        _, libname = it_lib.rsplit('/', 1)
                        libs.append(libname)

        self.assertListEqual(self._expected_link_order, libs)

    def test_cmake(self):
        t = TestClient(cache_folder=self._cache_folder)
        t.save({
            'conanfile.txt': textwrap.dedent("""
                [requires]
                libD/version
                [generators]
                cmake
                """),
            'CMakeLists.txt': textwrap.dedent("""
                cmake_minimum_required(VERSION 2.8.12)
                project(executable CXX)

                include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
                conan_basic_setup(TARGETS)
                
                add_executable(example main.cpp)
                target_link_libraries(example CONAN_PKG::libD)
                """),
            'main.cpp': textwrap.dedent("""
                int main() {return 0;}
                """)
        })

        t.run("install .")
        t.run_command("cmake . -DCMAKE_MODULE_PATH=. -DCMAKE_VERBOSE_MAKEFILE:BOOL=True")
        t.run_command("cmake --build .")

        # Get the actual link order from the CMake call
        libs = []
        for it in str(t.out).splitlines():
            if 'main.cpp.o  -o bin/example' in it:
                _, links = it.split("main.cpp.o  -o bin/example")
                for it_lib in links.split():
                    if it_lib.startswith("-l"):
                        libs.append(it_lib[2:])
                    else:
                        _, libname = it_lib.rsplit('/', 1)
                        libs.append(libname)

        self.assertListEqual(self._expected_link_order, libs)
