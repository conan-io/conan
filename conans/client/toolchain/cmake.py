# coding=utf-8
import os
import textwrap
from collections import OrderedDict, defaultdict

from jinja2 import Template

from conans.client.build.cmake_flags import get_generator, get_generator_platform, \
    CMakeDefinitionsBuilder, get_toolset, is_multi_configuration
from conans.client.generators.cmake_common import CMakeCommonMacros
from conans.util.files import save


# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


class Definitions(OrderedDict):
    _configuration_types = None  # Needed for py27 to avoid infinite recursion

    def __init__(self):
        super(Definitions, self).__init__()
        self._configuration_types = {}

    def __getattribute__(self, config):
        try:
            return super(Definitions, self).__getattribute__(config)
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

    _conan_set_libcxx = textwrap.dedent("""
        macro(conan_set_libcxx)
            if(DEFINED CONAN_LIBCXX)
                conan_message(STATUS "Conan: C++ stdlib: ${CONAN_LIBCXX}")
                if(CONAN_COMPILER STREQUAL "clang" OR CONAN_COMPILER STREQUAL "apple-clang")
                    if(CONAN_LIBCXX STREQUAL "libstdc++" OR CONAN_LIBCXX STREQUAL "libstdc++11" )
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -stdlib=libstdc++")
                    elseif(CONAN_LIBCXX STREQUAL "libc++")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -stdlib=libc++")
                    endif()
                endif()
                if(CONAN_COMPILER STREQUAL "sun-cc")
                    if(CONAN_LIBCXX STREQUAL "libCstd")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -library=Cstd")
                    elseif(CONAN_LIBCXX STREQUAL "libstdcxx")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -library=stdcxx4")
                    elseif(CONAN_LIBCXX STREQUAL "libstlport")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -library=stlport4")
                    elseif(CONAN_LIBCXX STREQUAL "libstdc++")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -library=stdcpp")
                    endif()
                endif()
                if(CONAN_LIBCXX STREQUAL "libstdc++11")
                    add_definitions(-D_GLIBCXX_USE_CXX11_ABI=1)
                elseif(CONAN_LIBCXX STREQUAL "libstdc++")
                    add_definitions(-D_GLIBCXX_USE_CXX11_ABI=0)
                endif()
            endif()
        endmacro()
    """)

    _template_toolchain = textwrap.dedent("""
        # Conan generated toolchain file
        cmake_minimum_required(VERSION 3.0)  # Needed for targets

        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        if(CONAN_TOOLCHAIN_INCLUDED)
          return()
        endif()
        set(CONAN_TOOLCHAIN_INCLUDED TRUE)

        ########### Utility macros and functions ###########
        {{ cmake_macros_and_functions }}
        ########### End of Utility macros and functions ###########

        # Configure
        {% if generator_platform %}
        set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE)
        {% endif %}
        {% if toolset %}
        set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}" CACHE STRING "" FORCE)
        {% endif%}

        # build_type (Release, Debug, etc) is only defined for single-config generators
        {% if build_type %}
        set(CMAKE_BUILD_TYPE "{{ build_type }}" CACHE STRING "Choose the type of build." FORCE)
        {% endif %}

        # --  - CMake.flags --> CMakeDefinitionsBuilder::get_definitions
        {%- for it, value in definitions.items() %}
        {%- if it.startswith('CONAN_') %}
        set({{ it }} "{{ value }}")
        {%- else %}
        set({{ it }} "{{ value }}" CACHE STRING "Value assigned from the Conan toolchain" FORCE)
        {%- endif %}
        {%- endfor %}

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
         # To support the cmake_find_package generators:
        {% if cmake_module_path %}
        set(CMAKE_MODULE_PATH {{ cmake_module_path }} ${CMAKE_MODULE_PATH})
        {% endif%}
        {% if cmake_prefix_path %}
        set(CMAKE_PREFIX_PATH {{ cmake_prefix_path }} ${CMAKE_PREFIX_PATH})
        {% endif%}

        {% if fpic %}
        message(STATUS "Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE=ON (options.fPIC)")
        set(CMAKE_POSITION_INDEPENDENT_CODE ON)
        {% endif %}

        {% if set_rpath %}conan_set_rpath(){% endif %}
        {% if set_std %}conan_set_std(){% endif %}
        {% if set_libcxx %}conan_set_libcxx(){% endif %}
        {% if install_prefix %}
        set(CMAKE_INSTALL_PREFIX {{install_prefix}} CACHE STRING "" FORCE)
        {% endif %}

        # Variables scoped to a configuration
        {%- for it, values in configuration_types_definitions.items() -%}
            {%- set genexpr = namespace(str='') %}
            {%- for conf, value in values -%}
                {%- set genexpr.str = genexpr.str +
                                      '$<IF:$<CONFIG:' + conf + '>,"' + value|string + '",' %}
                {%- if loop.last %}{% set genexpr.str = genexpr.str + '""' %}{% endif %}
            {%- endfor -%}
            {% for i in range(values|count) %}{%- set genexpr.str = genexpr.str + '>' %}{% endfor %}
        set({{ it }} {{ genexpr.str }})
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
        {{ cmake_macros_and_functions }}
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
                 cmake_system_name=True, toolset=None, parallel=True, make_program=None,
                 # cmake_program=None,  # TODO: cmake program should be considered in the environment
                 ):
        self._conanfile = conanfile

        self._fpic = self._deduce_fpic()
        self._vs_static_runtime = self._deduce_vs_static_runtime()

        self._set_rpath = True
        self._set_std = True
        self._set_libcxx = True

        # To find the generated cmake_find_package finders
        self._cmake_prefix_path = "${CMAKE_BINARY_DIR}"
        self._cmake_module_path = "${CMAKE_BINARY_DIR}"

        self._generator = generator or get_generator(self._conanfile)
        self._generator_platform = (generator_platform or
                                    get_generator_platform(self._conanfile.settings,
                                                           self._generator))
        self._toolset = toolset or get_toolset(self._conanfile.settings, self._generator)
        self._build_type = build_type or self._conanfile.settings.get_safe("build_type")

        builder = CMakeDefinitionsBuilder(self._conanfile,
                                          cmake_system_name=cmake_system_name,
                                          make_program=make_program, parallel=parallel,
                                          generator=self._generator,
                                          set_cmake_flags=False,
                                          output=self._conanfile.output)
        self.definitions = Definitions()
        self.definitions.update(builder.get_definitions())
        # FIXME: Removing too many things. We want to bring the new logic for the toolchain here
        # so we don't mess with the common code.
        self.definitions.pop("CMAKE_BUILD_TYPE", None)
        self.definitions.pop("CONAN_IN_LOCAL_CACHE", None)
        self.definitions.pop("CMAKE_PREFIX_PATH", None)
        self.definitions.pop("CMAKE_MODULE_PATH", None)
        self.definitions.pop("CONAN_LINK_RUNTIME", None)
        for install in ("PREFIX", "BINDIR", "SBINDIR", "LIBEXECDIR", "LIBDIR", "INCLUDEDIR",
                        "OLDINCLUDEDIR", "DATAROOTDIR"):
            self.definitions.pop("CMAKE_INSTALL_%s" % install, None)

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

    def _deduce_vs_static_runtime(self):
        settings = self._conanfile.settings
        if (settings.get_safe("compiler") == "Visual Studio" and
                "MT" in settings.get_safe("compiler.runtime")):
            return True
        return False

    def write_toolchain_files(self):
        # Make it absolute, wrt to current folder, set by the caller
        conan_project_include_cmake = os.path.abspath("conan_project_include.cmake")
        conan_project_include_cmake = conan_project_include_cmake.replace("\\", "/")
        t = Template(self._template_project_include)
        content = t.render(configuration_types_definitions=self.definitions.configuration_types,
                           vs_static_runtime=self._vs_static_runtime)
        save(conan_project_include_cmake, content)

        # TODO: I need the profile_host and profile_build here!
        # TODO: What if the compiler is a build require?
        # TODO: Add all the stuff related to settings (ALL settings or just _MY_ settings?)
        # TODO: I would want to have here the path to the compiler too
        build_type = self._build_type if not is_multi_configuration(self._generator) else None
        try:
            # This is only defined in the cache, not in the local flow
            install_prefix = self._conanfile.package_folder.replace("\\", "/")
        except AttributeError:
            # FIXME: In the local flow, we don't know the package_folder
            install_prefix = None
        context = {
            "configuration_types_definitions": self.definitions.configuration_types,
            "build_type": build_type,
            "generator_platform": self._generator_platform,
            "toolset": self._toolset,
            "definitions": self.definitions,
            "cmake_prefix_path": self._cmake_prefix_path,
            "cmake_module_path": self._cmake_module_path,
            "fpic": self._fpic,
            "set_rpath": self._set_rpath,
            "set_std": self._set_std,
            "set_libcxx": self._set_libcxx,
            "install_prefix": install_prefix
        }
        t = Template(self._template_toolchain)
        content = t.render(conan_project_include_cmake=conan_project_include_cmake,
                           cmake_macros_and_functions="\n".join([
                               CMakeCommonMacros.conan_message,
                               CMakeCommonMacros.conan_get_policy,
                               CMakeCommonMacros.conan_set_rpath,
                               CMakeCommonMacros.conan_set_std,
                               self._conan_set_libcxx,
                           ]),
                           **context)
        save(self.filename, content)
