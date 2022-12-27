import os
import platform
import re
import textwrap

import pytest
from jinja2 import Template

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient

"""
Check that the link order of libraries is preserved when using CMake generators
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
            self.cpp_info.includedirs = []
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
            self.cpp_info.includedirs = []
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


@pytest.fixture(scope="module")
def client():
    libZ_ref = ConanFileReference.loads("libZ/version")
    libH2_ref = ConanFileReference.loads("header2/version")
    libH_ref = ConanFileReference.loads("header/version")
    libA_ref = ConanFileReference.loads("libA/version")
    libB_ref = ConanFileReference.loads("libB/version")
    libC_ref = ConanFileReference.loads("libC/version")
    libD_ref = ConanFileReference.loads("libD/version")

    t = TestClient(path_with_spaces=False)
    t.save({
        'libZ/conanfile.py': conanfile.render(
            ref=libZ_ref,
            libs_extra=["Z2"],
            system_libs=["system_lib"],
            frameworks=["Carbon"]),
        'libH2/conanfile.py': conanfile_headeronly.render(
            ref=libH2_ref,
            system_libs=["header2_system_lib"],
            frameworks=["Security"]),
        'libH/conanfile.py': conanfile_headeronly.render(
            ref=libH_ref,
            requires=[libH2_ref, libZ_ref],
            system_libs=["header_system_lib"],
            frameworks=["CoreAudio"]),
        'libA/conanfile.py': conanfile.render(
            ref=libA_ref,
            requires=[libH_ref],
            libs_extra=["A2"],
            system_libs=["system_lib"],
            frameworks=["Carbon"]),
        'libB/conanfile.py': conanfile.render(
            ref=libB_ref,
            requires=[libA_ref],
            libs_extra=["B2"],
            system_libs=["system_lib"],
            frameworks=["Carbon"]),
        'libC/conanfile.py': conanfile.render(
            ref=libC_ref,
            requires=[libA_ref],
            libs_extra=["C2"],
            system_libs=["system_lib"],
            frameworks=["Carbon"]),
        'libD/conanfile.py': conanfile.render(
            ref=libD_ref,
            requires=[libB_ref, libC_ref],
            libs_extra=["D2"],
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
    return t


def _validate_link_order(libs):
    # Check that all the libraries are there:
    assert len(libs) == 16 if platform.system() == "Darwin" else (13 if platform.system() == "Linux"
                                                                  else 23)
    # - Regular libs
    ext = ".lib" if platform.system() == "Windows" else ".a"
    prefix = "" if platform.system() == "Windows" else "lib"
    expected_libs = {prefix + it + ext for it in ['libD', 'D2', 'libB', 'B2', 'libC', 'C2',
                                                  'libA', 'A2', 'libZ', 'Z2']}
    # - System libs
    ext_system = ".lib" if platform.system() == "Windows" else ""
    expected_libs.update([it + ext_system for it in ['header_system_lib',
                                                     'header2_system_lib',
                                                     'system_lib']])
    # - Add MacOS frameworks
    if platform.system() == "Darwin":
        expected_libs.update(['CoreAudio', 'Security', 'Carbon'])
    # - Add Windows libs
    if platform.system() == "Windows":
        expected_libs.update(['kernel32.lib', 'user32.lib', 'gdi32.lib', 'winspool.lib',
                              'shell32.lib', 'ole32.lib', 'oleaut32.lib', 'uuid.lib',
                              'comdlg32.lib', 'advapi32.lib'])
    assert set(libs) == expected_libs

    # These are the first libraries and order is mandatory
    mandatory_1 = [prefix + it + ext for it in ['libD', 'D2', 'libB', 'B2', 'libC',
                                                'C2', 'libA', 'A2', ]]
    assert mandatory_1 == libs[:len(mandatory_1)]

    # Then, libZ ones must be before system libraries that are consuming
    assert libs.index(prefix + 'libZ' + ext) < libs.index('system_lib' + ext_system)
    assert libs.index(prefix + 'Z2' + ext) < libs.index('system_lib' + ext_system)

    if platform.system() == "Darwin":
       assert libs.index('liblibZ.a') < libs.index('Carbon')
       assert libs.index('libZ2.a') < libs.index('Carbon')


def _get_link_order_from_cmake(content):
    libs = []
    for it in content.splitlines():
        # This is for Linux and Mac
        # Remove double spaces from output that appear in some platforms
        line = ' '.join(it.split())
        if 'main.cpp.o -o example' in line:
            _, links = line.split("main.cpp.o -o example")
            for it_lib in links.split():
                if it_lib.startswith("-L") or it_lib.startswith("-Wl,-rpath"):
                    continue
                elif it_lib.startswith("-l"):
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


def _get_link_order_from_xcode(content):
    libs = []

    # Find the right Release block in the XCode file
    results = re.finditer('/\* Release \*/ = {', content)
    for r in results:
        release_section = content[r.start():].split("name = Release;", 1)[0]
        if "-headerpad_max_install_names" in release_section:
            break
    else:
        raise Exception("Cannot find the Release block linking the expected libraries")

    start_key = '-Wl,-headerpad_max_install_names'
    end_key = ');'
    libs_content = release_section.split(start_key, 1)[1].split(end_key, 1)[0]
    libs_unstripped = libs_content.split(",")
    for lib in libs_unstripped:
        if ".a" in lib:
            libs.append(lib.strip('"').rsplit('/', 1)[1])
        elif "-l" in lib:
            libs.append(lib.strip('"')[2:])
        elif "-framework" in lib:
            libs.append(lib.strip('"')[11:])
    return libs


def _create_find_package_project(client):
    t = TestClient(cache_folder=client.cache_folder)
    t.save({
        'conanfile.txt': textwrap.dedent("""
            [requires]
            libD/version
            [generators]
            CMakeDeps
            CMakeToolchain
            """),
        'CMakeLists.txt': textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(executable CXX)

            find_package(libD)
            add_executable(example main.cpp)
            target_link_libraries(example libD::libD)
            """),
        'main.cpp': main_cpp
    })

    t.run("install . -s build_type=Release")
    return t


def _run_and_get_lib_order(t, generator):
    if generator == "Xcode":
        t.run_command("cmake . -G Xcode -DCMAKE_VERBOSE_MAKEFILE:BOOL=True"
                      " -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake")
        # This is building by default the Debug configuration that contains nothing, so it works
        t.run_command("cmake --build .")
        # This is building the release and fails because invented system libraries are missing
        t.run_command("cmake --build . --config Release", assert_error=True)
        # Get the actual link order from the CMake call
        libs = _get_link_order_from_xcode(t.load(os.path.join('executable.xcodeproj',
                                                              'project.pbxproj')))
    else:
        t.run_command("cmake . -DCMAKE_VERBOSE_MAKEFILE:BOOL=True"
                      " -DCMAKE_BUILD_TYPE=Release"
                      " -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake")
        extra_build = "--config Release" if platform.system() == "Windows" else ""  # Windows VS
        t.run_command("cmake --build . {}".format(extra_build), assert_error=True)
        # Get the actual link order from the CMake call
        libs = _get_link_order_from_cmake(str(t.out))
    return libs


@pytest.mark.parametrize("generator", [None, "Xcode"])
@pytest.mark.tool_cmake(version="3.19")
def test_cmake_deps(client, generator):
    if generator == "Xcode" and platform.system() != "Darwin":
        pytest.skip("Xcode is needed")

    t = _create_find_package_project(client)
    libs = _run_and_get_lib_order(t, generator)
    _validate_link_order(libs)
