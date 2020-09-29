import os
import textwrap
from collections import OrderedDict, defaultdict

from jinja2 import Template

from conans.client.build.cmake_flags import get_generator, get_generator_platform,  get_toolset, \
    is_multi_configuration
from conans.client.build.compiler_flags import architecture_flag
from conans.client.tools import cpu_count
from conans.errors import ConanException
from conans.util.files import save


# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


class Variables(OrderedDict):
    _configuration_types = None  # Needed for py27 to avoid infinite recursion

    def __init__(self):
        super(Variables, self).__init__()
        self._configuration_types = {}

    def __getattribute__(self, config):
        try:
            return super(Variables, self).__getattribute__(config)
        except AttributeError:
            return self._configuration_types.setdefault(config, dict())

    @property
    def configuration_types(self):
        # Reverse index for the configuration_types variables
        ret = defaultdict(list)
        for conf, definitions in self._configuration_types.items():
            for k, v in definitions.items():
                ret[k].append((conf, v))
        return ret


class CMakeToolchain(object):
    filename = "conan_toolchain.cmake"

    _template_toolchain = textwrap.dedent("""
        # Conan automatically generated toolchain file
        # DO NOT EDIT MANUALLY, it will be overwritten

        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        if(CONAN_TOOLCHAIN_INCLUDED)
          return()
        endif()
        set(CONAN_TOOLCHAIN_INCLUDED TRUE)

        # Configure
        {%- if generator_platform %}
        set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE)
        {%- endif %}
        {%- if toolset %}
        set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}" CACHE STRING "" FORCE)
        {%- endif %}

        # build_type (Release, Debug, etc) is only defined for single-config generators
        {%- if build_type %}
        set(CMAKE_BUILD_TYPE "{{ build_type }}" CACHE STRING "Choose the type of build." FORCE)
        {%- endif %}

        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(_CMAKE_IN_TRY_COMPILE)
            message(STATUS "Running toolchain IN_TRY_COMPILE")
            return()
        endif()

        message("Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")

        if(CMAKE_VERSION VERSION_LESS "3.15")
            message(WARNING
                " CMake version less than 3.15 doesn't support CMAKE_PROJECT_INCLUDE variable\\n"
                " used by Conan toolchain to work. In order to get the same behavior you will\\n"
                " need to manually include the generated file after your 'project()' call in the\\n"
                " main CMakeLists.txt file:\\n"
                " \\n"
                "     project(YourProject C CXX)\\n"
                "     include(\\"\\${CMAKE_BINARY_DIR}/conan_project_include.cmake\\")\\n"
                " \\n"
                " This file contains some definitions and extra adjustments that depend on\\n"
                " the build_type and it cannot be done in the toolchain.")
        else()
            # Will be executed after the 'project()' command
            set(CMAKE_PROJECT_INCLUDE "{{ conan_project_include_cmake }}")
        endif()

        # We are going to adjust automagically many things as requested by Conan
        #   these are the things done by 'conan_basic_setup()'
        set(CMAKE_EXPORT_NO_PACKAGE_REGISTRY ON)

        # To support the cmake_find_package generators
        {% if cmake_module_path -%}
        set(CMAKE_MODULE_PATH {{ cmake_module_path }} ${CMAKE_MODULE_PATH})
        {%- endif %}
        {% if cmake_prefix_path -%}
        set(CMAKE_PREFIX_PATH {{ cmake_prefix_path }} ${CMAKE_PREFIX_PATH})
        {%- endif %}

        # shared libs
        {% if shared_libs -%}
        message(STATUS "Conan toolchain: Setting BUILD_SHARED_LIBS= {{ shared_libs }}")
        set(BUILD_SHARED_LIBS {{ shared_libs }})
        {%- endif %}

        # fPIC
        {% if fpic -%}
        message(STATUS "Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE=ON (options.fPIC)")
        set(CMAKE_POSITION_INDEPENDENT_CODE ON)
        {%- endif %}

        # SKIP_RPATH
        {% if skip_rpath -%}
        set(CMAKE_SKIP_RPATH 1 CACHE BOOL "rpaths" FORCE)
        # Policy CMP0068
        # We want the old behavior, in CMake >= 3.9 CMAKE_SKIP_RPATH won't affect install_name in OSX
        set(CMAKE_INSTALL_NAME_DIR "")
        {% endif -%}

        # Parallel builds
        {% if parallel -%}
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ parallel }}")
        set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ parallel }}")
        {%- endif %}

        # Architecture
        {% if architecture -%}
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ architecture }}")
        set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ architecture }}")
        set(CONAN_SHARED_LINKER_FLAGS "${CONAN_SHARED_LINKER_FLAGS} {{ architecture }}")
        set(CONAN_EXE_LINKER_FLAGS "${CONAN_EXE_LINKER_FLAGS} {{ architecture }}")
        {%- endif %}

        # C++ Standard Library
        {% if set_libcxx -%}
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ set_libcxx }}")
        {%- endif %}
        {% if glibcxx -%}
        add_definitions(-D_GLIBCXX_USE_CXX11_ABI={{ glibcxx }})
        {%- endif %}

        # C++ Standard
        {% if cppstd -%}
        message(STATUS "Conan C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}}")
        set(CMAKE_CXX_STANDARD {{ cppstd }})
        set(CMAKE_CXX_EXTENSIONS {{ cppstd_extensions }})
        {%- endif %}

        # Install prefix
        {% if install_prefix -%}
        set(CMAKE_INSTALL_PREFIX {{install_prefix}} CACHE STRING "" FORCE)
        {%- endif %}

        # Variables
        {% for it, value in variables.items() -%}
        set({{ it }} "{{ value }}")
        {%- endfor %}
        # Variables  per configuration
        {% for it, values in variables_config.items() -%}
            {%- set genexpr = namespace(str='') %}
            {%- for conf, value in values -%}
                {%- set genexpr.str = genexpr.str +
                                      '$<IF:$<CONFIG:' + conf + '>,"' + value|string + '",' %}
                {%- if loop.last %}{% set genexpr.str = genexpr.str + '""' -%}{%- endif -%}
            {%- endfor -%}
            {% for i in range(values|count) %}{%- set genexpr.str = genexpr.str + '>' %}
            {%- endfor -%}
        set({{ it }} {{ genexpr.str }})
        {%- endfor %}

        # Preprocessor definitions
        {% for it, value in preprocessor_definitions.items() -%}
        # add_compile_definitions only works in cmake >= 3.12
        add_definitions(-D{{ it }}="{{ value }}")
        {%- endfor %}
        # Preprocessor definitions per configuration
        {% for it, values in preprocessor_definitions_config.items() -%}
            {%- set genexpr = namespace(str='') %}
            {%- for conf, value in values -%}
                {%- set genexpr.str = genexpr.str +
                                      '$<IF:$<CONFIG:' + conf + '>,"' + value|string + '",' %}
                {%- if loop.last %}{% set genexpr.str = genexpr.str + '""' -%}{%- endif -%}
            {%- endfor -%}
            {% for i in range(values|count) %}{%- set genexpr.str = genexpr.str + '>' %}
            {%- endfor -%}
        add_definitions(-D{{ it }}={{ genexpr.str }})
        {%- endfor %}


        set(CMAKE_CXX_FLAGS_INIT "${CONAN_CXX_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_C_FLAGS_INIT "${CONAN_C_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_SHARED_LINKER_FLAGS_INIT "${CONAN_SHARED_LINKER_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_EXE_LINKER_FLAGS_INIT "${CONAN_EXE_LINKER_FLAGS}" CACHE STRING "" FORCE)
    """)

    _template_project_include = textwrap.dedent("""
        # When using a Conan toolchain, this file is included as the last step of `project()` calls.
        #  https://cmake.org/cmake/help/latest/variable/CMAKE_PROJECT_INCLUDE.html

        if (NOT CONAN_TOOLCHAIN_INCLUDED)
            message(FATAL_ERROR "This file is expected to be used together with the Conan toolchain")
        endif()

        ########### Utility macros and functions ###########
        function(conan_get_policy policy_id policy)
            if(POLICY "${policy_id}")
                cmake_policy(GET "${policy_id}" _policy)
                set(${policy} "${_policy}" PARENT_SCOPE)
            else()
                set(${policy} "" PARENT_SCOPE)
            endif()
        endfunction()
        ########### End of Utility macros and functions ###########

        # Adjustments that depends on the build_type
        {% if vs_static_runtime %}
        conan_get_policy(CMP0091 policy_0091)
        if(policy_0091 STREQUAL "NEW")
            set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
        else()
            foreach(flag CMAKE_C_FLAGS_RELEASE CMAKE_CXX_FLAGS_RELEASE
                         CMAKE_C_FLAGS_RELWITHDEBINFO CMAKE_CXX_FLAGS_RELWITHDEBINFO
                         CMAKE_C_FLAGS_MINSIZEREL CMAKE_CXX_FLAGS_MINSIZEREL
                         CMAKE_C_FLAGS_DEBUG CMAKE_CXX_FLAGS_DEBUG)
                if(DEFINED ${flag})
                    string(REPLACE "/MD" "/MT" ${flag} "${${flag}}")
                endif()
            endforeach()
        endif()
        {% endif %}
    """)

    def __init__(self, conanfile, generator=None, generator_platform=None, build_type=None,
                 toolset=None, parallel=True):
        self._conanfile = conanfile

        self.fpic = self._deduce_fpic()
        self.vs_static_runtime = self._deduce_vs_static_runtime()
        self.parallel = parallel

        # To find the generated cmake_find_package finders
        self.cmake_prefix_path = "${CMAKE_BINARY_DIR}"
        self.cmake_module_path = "${CMAKE_BINARY_DIR}"

        self.generator = generator or get_generator(self._conanfile)
        self.generator_platform = (generator_platform or
                                   get_generator_platform(self._conanfile.settings,
                                                          self.generator))
        self.toolset = toolset or get_toolset(self._conanfile.settings, self.generator)

        self.variables = Variables()
        self.preprocessor_definitions = Variables()
        try:
            self._build_shared_libs = "ON" if self._conanfile.options.shared else "OFF"
        except ConanException:
            self._build_shared_libs = None

        self.set_libcxx, self.glibcxx = self._get_libcxx()

        self.parallel = None
        if parallel:
            if self.generator and "Visual Studio" in self.generator:
                self.parallel = "/MP%s" % cpu_count(output=self._conanfile.output)

        self.cppstd, self.cppstd_extensions = self._cppstd()

        self.skip_rpath = True if self._conanfile.settings.get_safe("os") == "Macos" else False
        self.architecture = self._get_architecture()

        # TODO: I would want to have here the path to the compiler too
        build_type = build_type or self._conanfile.settings.get_safe("build_type")
        self.build_type = build_type if not is_multi_configuration(self.generator) else None
        try:
            # This is only defined in the cache, not in the local flow
            self.install_prefix = self._conanfile.package_folder.replace("\\", "/")
        except AttributeError:
            # FIXME: In the local flow, we don't know the package_folder
            self.install_prefix = None

    def _deduce_fpic(self):
        fpic = self._conanfile.options.get_safe("fPIC")
        if fpic is None:
            return None
        os_ = self._conanfile.settings.get_safe("os")
        if os_ and "Windows" in os_:
            self._conanfile.output.warn("Toolchain: Ignoring fPIC option defined for Windows")
            return None
        shared = self._conanfile.options.get_safe("shared")
        if shared:
            self._conanfile.output.warn("Toolchain: Ignoring fPIC option defined "
                                        "for a shared library")
            return None
        return fpic

    def _get_architecture(self):
        # This should be factorized and make it toolchain-private
        return architecture_flag(self._conanfile.settings)

    def _deduce_vs_static_runtime(self):
        settings = self._conanfile.settings
        if (settings.get_safe("compiler") == "Visual Studio" and
                "MT" in settings.get_safe("compiler.runtime")):
            return True
        return False

    def _get_libcxx(self):
        libcxx = self._conanfile.settings.get_safe("compiler.libcxx")
        if not libcxx:
            return None, None
        compiler = self._conanfile.settings.compiler
        lib = glib = None
        if compiler == "apple-clang":
            # In apple-clang 2 only values atm are "libc++" and "libstdc++"
            lib = "-stdlib={}".format(libcxx)
        elif compiler == "clang":
            if libcxx == "libc++":
                lib = "-stdlib=libc++"
            elif libcxx == "libstdc++" or libcxx == "libstdc++11":
                lib = "-stdlib=libstdc++"
            # FIXME, something to do with the other values? Android c++_shared?
        elif compiler == "sun-cc":
            lib = {"libCstd": "Cstd",
                   "libstdcxx": "stdcxx4",
                   "libstlport": "stlport4",
                   "libstdc++": "stdcpp"
                   }.get(libcxx)
            if lib:
                lib = "-library={}".format(lib)
        elif compiler == "gcc":
            if libcxx == "libstdc++11":
                glib = "1"
            elif libcxx == "libstdc++":
                glib = "0"
        return lib, glib

    def _cppstd(self):
        cppstd = cppstd_extensions = None
        compiler_cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        if compiler_cppstd:
            if compiler_cppstd.startswith("gnu"):
                cppstd = compiler_cppstd[3:]
                cppstd_extensions = "ON"
            else:
                cppstd = compiler_cppstd
                cppstd_extensions = "OFF"
        return cppstd, cppstd_extensions

    def write_toolchain_files(self):
        # Make it absolute, wrt to current folder, set by the caller
        conan_project_include_cmake = os.path.abspath("conan_project_include.cmake")
        conan_project_include_cmake = conan_project_include_cmake.replace("\\", "/")
        t = Template(self._template_project_include)
        content = t.render(vs_static_runtime=self.vs_static_runtime)
        save(conan_project_include_cmake, content)

        # TODO: I need the profile_host and profile_build here!
        # TODO: What if the compiler is a build require?
        # TODO: Add all the stuff related to settings (ALL settings or just _MY_ settings?)

        context = {
            "variables": self.variables,
            "variables_config": self.variables.configuration_types,
            "preprocessor_definitions": self.preprocessor_definitions,
            "preprocessor_definitions_config": self.preprocessor_definitions.configuration_types,
            "build_type": self.build_type,
            "generator_platform": self.generator_platform,
            "toolset": self.toolset,
            "cmake_prefix_path": self.cmake_prefix_path,
            "cmake_module_path": self.cmake_module_path,
            "fpic": self.fpic,
            "skip_rpath": self.skip_rpath,
            "set_libcxx": self.set_libcxx,
            "glibcxx": self.glibcxx,
            "install_prefix": self.install_prefix,
            "parallel": self.parallel,
            "cppstd": self.cppstd,
            "cppstd_extensions": self.cppstd_extensions,
            "shared_libs": self._build_shared_libs,
            "architecture": self.architecture
        }
        t = Template(self._template_toolchain)
        content = t.render(conan_project_include_cmake=conan_project_include_cmake, **context)
        save(self.filename, content)
