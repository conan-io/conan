import os
import re

from jinja2 import Template

from conans import __version__ as client_version
from conans.client.cmd.new_ci import ci_get_files
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, get_reference_fields
from conans.util.files import load


conanfile = """from conans import ConanFile, CMake, tools


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False], "fPIC": [True, False]}}
    default_options = {{"shared": False, "fPIC": True}}
    generators = "cmake"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def source(self):
        self.run("git clone https://github.com/conan-io/hello.git")
        # This small hack might be useful to guarantee proper /MT /MD linkage
        # in MSVC if the packaged project doesn't have variables to set it
        # properly
        tools.replace_in_file("hello/CMakeLists.txt", "PROJECT(HelloWorld)",
                              '''PROJECT(HelloWorld)
include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()''')

    def build(self):
        cmake = CMake(self)
        cmake.configure(source_folder="hello")
        cmake.build()

        # Explicit way:
        # self.run('cmake %s/hello %s'
        #          % (self.source_folder, cmake.command_line))
        # self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        self.copy("*.h", dst="include", src="hello")
        self.copy("*hello.lib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)
        self.copy("*.so", dst="lib", keep_path=False)
        self.copy("*.dylib", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["hello"]

"""

conanfile_bare = """from conans import ConanFile, tools


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    settings = "os", "compiler", "build_type", "arch"
    description = "<Description of {package_name} here>"
    url = "None"
    license = "None"
    author = "None"
    topics = None

    def package(self):
        self.copy("*")

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
"""

conanfile_sources = """from conans import ConanFile, CMake


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False], "fPIC": [True, False]}}
    default_options = {{"shared": False, "fPIC": True}}
    generators = "cmake"
    exports_sources = "src/*"
{configure}
    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def build(self):
        cmake = CMake(self)
        cmake.configure(source_folder="src")
        cmake.build()

        # Explicit way:
        # self.run('cmake %s/hello %s'
        #          % (self.source_folder, cmake.command_line))
        # self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        self.copy("*.h", dst="include", src="src")
        self.copy("*.lib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)
        self.copy("*.dylib*", dst="lib", keep_path=False)
        self.copy("*.so", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["{name}"]
"""

conanfile_header = """import os

from conans import ConanFile, tools


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")
    no_copy_source = True
    # No settings/options are necessary, this is header only

    def source(self):
        '''retrieval of the source code here. Remember you can also put the code
        in the folder and use exports instead of retrieving it with this
        source() method
        '''
        # self.run("git clone ...") or
        # tools.download("url", "file.zip")
        # tools.unzip("file.zip" )

    def package(self):
        self.copy("*.h", "include")

    def package_id(self):
        self.info.header_only()
"""


test_conanfile = """import os

from conans import ConanFile, CMake, tools


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        # Current dir is "test_package/build/<build_id>" and CMakeLists.txt is
        # in "test_package"
        cmake.configure()
        cmake.build()

    def imports(self):
        self.copy("*.dll", dst="bin", src="bin")
        self.copy("*.dylib*", dst="bin", src="lib")
        self.copy('*.so*', dst='bin', src='lib')

    def test(self):
        if not tools.cross_building(self):
            os.chdir("bin")
            self.run(".%sexample" % os.sep)
"""

test_cmake = """cmake_minimum_required(VERSION 3.1)
project(PackageTest CXX)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

add_executable(example example.cpp)
target_link_libraries(example ${CONAN_LIBS})

# CTest is a testing tool that can be used to test your project.
# enable_testing()
# add_test(NAME example
#          WORKING_DIRECTORY ${CMAKE_BINARY_DIR}/bin
#          COMMAND example)
"""

test_cmake_pure_c = """cmake_minimum_required(VERSION 3.1)
project(PackageTest C)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

add_executable(example example.c)
target_link_libraries(example ${CONAN_LIBS})

# CTest is a testing tool that can be used to test your project.
# enable_testing()
# add_test(NAME example
#          WORKING_DIRECTORY ${CMAKE_BINARY_DIR}/bin
#          COMMAND example)
"""

test_main = """#include "{name}.h"

int main() {{
    {name}();
}}
"""

hello_c = """ #include <stdio.h>
#include "{name}.h"

void {name}() {{
    int class = 0;  //This will be an error in C++
    #ifdef NDEBUG
        printf("{name}/{version}-(pure C): Hello World Release!\\n");
    #else
        printf("{name}/{version}-(pure C): Hello World Debug!\\n");
    #endif
}}
"""

hello_h = """#pragma once

#ifdef WIN32
  #define {name}_EXPORT __declspec(dllexport)
#else
  #define {name}_EXPORT
#endif

{name}_EXPORT void {name}();
"""

hello_cpp = """#include <iostream>
#include "{name}.h"

void {name}(){{
    #ifdef NDEBUG
    std::cout << "{name}/{version}: Hello World Release!" <<std::endl;
    #else
    std::cout << "{name}/{version}: Hello World Debug!" <<std::endl;
    #endif
}}
"""

cmake_pure_c = """cmake_minimum_required(VERSION 3.1)
project({name} C)

include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()

add_library({name} {name}.c)
"""

cmake = """cmake_minimum_required(VERSION 3.1)
project({name} CXX)

include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()

add_library({name} {name}.cpp)
"""

gitignore_template = """
*.pyc
test_package/build

"""


def _render_template(text, name, version, package_name, defines):
    context = {'name': name,
               'version': version,
               'package_name': package_name,
               'conan_version': client_version}
    context.update(defines)
    t = Template(text, keep_trailing_newline=True)
    return t.render(**context)


def _get_files_from_template_dir(template_dir, name, version, package_name, defines):
    files = []
    for d, _, fs in os.walk(template_dir):
        for f in fs:
            rel_d = os.path.relpath(d, template_dir)
            rel_f = os.path.join(rel_d, f)
            files.append(rel_f)

    out_files = dict()
    for f in files:
        f_path = os.path.join(template_dir, f)
        rendered_path = _render_template(f, name=name, version=version, package_name=package_name,
                                         defines=defines)
        rendered_file = _render_template(load(f_path), name=name, version=version,
                                         package_name=package_name, defines=defines)
        out_files[rendered_path] = rendered_file

    return out_files


def cmd_new(ref, header=False, pure_c=False, test=False, exports_sources=False, bare=False,
            visual_versions=None, linux_gcc_versions=None, linux_clang_versions=None,
            osx_clang_versions=None, shared=None, upload_url=None, gitignore=None,
            gitlab_gcc_versions=None, gitlab_clang_versions=None,
            circleci_gcc_versions=None, circleci_clang_versions=None, circleci_osx_versions=None,
            template=None, cache=None, defines=None):
    try:
        name, version, user, channel, revision = get_reference_fields(ref, user_channel_input=False)
        # convert "package_name" -> "PackageName"
        package_name = re.sub(r"(?:^|[\W_])(\w)", lambda x: x.group(1).upper(), name)
    except ValueError:
        raise ConanException("Bad parameter, please use full package name,"
                             "e.g.: MyLib/1.2.3@user/testing")

    # Validate it is a valid reference
    ConanFileReference(name, version, user, channel)

    if header and exports_sources:
        raise ConanException("'header' and 'sources' are incompatible options")
    if pure_c and header:
        raise ConanException("'pure_c' is incompatible with 'header'")
    if pure_c and not exports_sources:
        raise ConanException("'pure_c' requires the use of --source")
    if bare and (header or exports_sources):
        raise ConanException("'bare' is incompatible with 'header' and 'sources'")
    if template and (header or exports_sources or bare or pure_c):
        raise ConanException("'template' is incompatible with 'header', "
                             "'sources', 'pure-c' and 'bare'")

    defines = defines or dict()

    if header:
        files = {"conanfile.py": conanfile_header.format(name=name, version=version,
                                                         package_name=package_name)}
    elif exports_sources:
        if not pure_c:
            files = {"conanfile.py": conanfile_sources.format(name=name, version=version,
                                                              package_name=package_name,
                                                              configure=""),
                     "src/{}.cpp".format(name): hello_cpp.format(name=name, version=version),
                     "src/{}.h".format(name): hello_h.format(name=name, version=version),
                     "src/CMakeLists.txt": cmake.format(name=name, version=version)}
        else:
            config = ("\n    def configure(self):\n"
                      "        del self.settings.compiler.libcxx\n"
                      "        del self.settings.compiler.cppstd\n")
            files = {"conanfile.py": conanfile_sources.format(name=name, version=version,
                                                              package_name=package_name,
                                                              configure=config),
                     "src/{}.c".format(name): hello_c.format(name=name, version=version),
                     "src/{}.h".format(name): hello_h.format(name=name, version=version),
                     "src/CMakeLists.txt": cmake_pure_c.format(name=name, version=version)}
    elif bare:
        files = {"conanfile.py": conanfile_bare.format(name=name, version=version,
                                                       package_name=package_name)}
    elif template:
        is_file_template = os.path.basename(template).endswith('.py')
        if is_file_template:
            if not os.path.isabs(template):
                # FIXME: Conan 2.0. The old path should be removed
                old_path = os.path.join(cache.cache_folder, "templates", template)
                new_path = os.path.join(cache.cache_folder, "templates", "command/new", template)
                template = new_path if os.path.isfile(new_path) else old_path
            if not os.path.isfile(template):
                raise ConanException("Template doesn't exist: %s" % template)
            replaced = _render_template(load(template),
                                        name=name,
                                        version=version,
                                        package_name=package_name,
                                        defines=defines)
            files = {"conanfile.py": replaced}
        elif template == "cmake_lib":
            from conans.assets.templates.new_v2_cmake import get_cmake_lib_files
            files = get_cmake_lib_files(name, version, package_name)
        elif template == "cmake_exe":
            from conans.assets.templates.new_v2_cmake import get_cmake_exe_files
            files = get_cmake_exe_files(name, version, package_name)
        elif template == "meson_lib":
            from conans.assets.templates.new_v2_meson import get_meson_lib_files
            files = get_meson_lib_files(name, version, package_name)
        elif template == "meson_exe":
            from conans.assets.templates.new_v2_meson import get_meson_exe_files
            files = get_meson_exe_files(name, version, package_name)
        elif template == "msbuild_lib":
            from conans.assets.templates.new_v2_msbuild import get_msbuild_lib_files
            files = get_msbuild_lib_files(name, version, package_name)
        elif template == "msbuild_exe":
            from conans.assets.templates.new_v2_msbuild import get_msbuild_exe_files
            files = get_msbuild_exe_files(name, version, package_name)
        elif template == "bazel_lib":
            from conans.assets.templates.new_v2_bazel import get_bazel_lib_files
            files = get_bazel_lib_files(name, version, package_name)
        elif template == "bazel_exe":
            from conans.assets.templates.new_v2_bazel import get_bazel_exe_files
            files = get_bazel_exe_files(name, version, package_name)
        elif template == "autotools_lib":
            from conans.assets.templates.new_v2_autotools import get_autotools_lib_files
            files = get_autotools_lib_files(name, version, package_name)
        elif template == "autotools_exe":
            from conans.assets.templates.new_v2_autotools import get_autotools_exe_files
            files = get_autotools_exe_files(name, version, package_name)
        else:
            if not os.path.isabs(template):
                template = os.path.join(cache.cache_folder, "templates", "command/new", template)
            if not os.path.isdir(template):
                raise ConanException("Template doesn't exist: {}".format(template))
            template = os.path.normpath(template)
            files = _get_files_from_template_dir(template_dir=template,
                                                 name=name,
                                                 version=version,
                                                 package_name=package_name,
                                                 defines=defines)
    else:
        files = {"conanfile.py": conanfile.format(name=name, version=version,
                                                  package_name=package_name)}

    if test:
        files["test_package/conanfile.py"] = test_conanfile.format(name=name, version=version,
                                                                   user=user, channel=channel,
                                                                   package_name=package_name)
        if pure_c:
            files["test_package/example.c"] = test_main.format(name=name)
            files["test_package/CMakeLists.txt"] = test_cmake_pure_c
        else:
            include_name = name if exports_sources else "hello"
            files["test_package/example.cpp"] = test_main.format(name=include_name)
            files["test_package/CMakeLists.txt"] = test_cmake

    if gitignore:
        files[".gitignore"] = gitignore_template

    files.update(ci_get_files(name, version, user, channel, visual_versions,
                              linux_gcc_versions, linux_clang_versions,
                              osx_clang_versions, shared, upload_url,
                              gitlab_gcc_versions, gitlab_clang_versions,
                              circleci_gcc_versions, circleci_clang_versions,
                              circleci_osx_versions))
    return files
