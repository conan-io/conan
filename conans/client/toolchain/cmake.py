# coding=utf-8

import os
import textwrap
from collections import OrderedDict, defaultdict

from jinja2 import Template

from conans.client.build.cmake_flags import get_generator, get_generator_platform, \
    CMakeDefinitionsBuilder, get_toolset


# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


class Definitions(OrderedDict):
    def __init__(self):
        self._configuration_types = {}

    def __getattr__(self, item):
        return self._configuration_types.setdefault(item, dict())

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
    conan_adjustements = os.path.join(os.path.dirname(__file__), "conan_adjustments.cmake")

    _template_toolchain = textwrap.dedent("""
        # Conan generated toolchain file
        
        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        if(CONAN_TOOLCHAIN_INCLUDED)
          return()
        endif()
        set(CONAN_TOOLCHAIN_INCLUDED true)

        message("Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")
        
        # Configure
        # -- CMake::command_line
        {% if generator_platform %}set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}"){% endif %}
        {% if toolset %}set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}"){% endif%}
        
        # --  - CMake.flags --> CMakeDefinitionsBuilder::get_definitions
        {%- for it, value in definitions.items() %}
        set({{ it }} "{{ value }}" CACHE STRING "Do we want to set all these vars in the cache?" FORCE)
        {%- endfor %}
        
        # Set some environment variables
        {%- for it, value in environment.items() %}
        set(ENV{{ '{' }}{{ it }}{{ '}' }} "{{ value }}")
        {%- endfor %}
        
        include("{{ conan_adjustements_cmake }}")
        
        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(NOT _CMAKE_IN_TRY_COMPILE)
            {% if options.set_vs_runtime %}
            set(CMAKE_PROJECT_INCLUDE "{{ conan_project_include_cmake }}")  # Will be executed after the project
            {%- endif %}

            # We are going to adjust automagically many things as requested by Conan
            #   these are the things done by 'conan_basic_setup()'            
            {% if options.set_rpath %}conan_set_rpath(){% endif %}
            {% if options.set_std %}conan_set_std(){% endif %}
            {% if options.set_fpic %}conan_set_fpic(){% endif %}
            
            #conan_check_compiler()
            {% if options.set_libcxx %}conan_set_libcxx(){% endif %}
            {% if options.set_find_paths %}conan_set_find_paths(){% endif %}
            {% if options.set_find_library_paths %}conan_set_find_library_paths(){% endif %}
            
            set(CMAKE_CXX_FLAGS_INIT "${CONAN_CXX_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_C_FLAGS_INIT "${CONAN_C_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_SHARED_LINKER_FLAGS_INIT "${CONAN_SHARED_LINKER_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_EXE_LINKER_FLAGS_INIT "${CONAN_EXE_LINKER_FLAGS}" CACHE STRING "" FORCE)
        endif()
        
        {% if options.set_compiler %}conan_set_compiler(){% endif %}
    """)

    _template_project_include = textwrap.dedent("""
        # When using a Conan toolchain, this file is included as the last step of all `project()` calls.
        #  https://cmake.org/cmake/help/latest/variable/CMAKE_PROJECT_INCLUDE.html

        include("{{ conan_adjustements_cmake }}")

        # Now the debug/release stuff
        # CMAKE_BUILD_TYPE: Use it only if it isn't a multi-config generator
        get_property(_GENERATOR_IS_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG )
        if(NOT _GENERATOR_IS_MULTI_CONFIG)
            set(CMAKE_BUILD_TYPE "{{ CMAKE_BUILD_TYPE }}" CACHE STRING "Choose the type of build." FORCE)
        endif()
        unset(_GENERATOR_IS_MULTI_CONFIG)
        
        # Variables scoped to a configuration
        {%- for it, values in configuration_types_definitions.items() -%}
            {%- set generator_expression = namespace(str='') %}
            {%- for conf, value in values -%}
                {%- set generator_expression.str = generator_expression.str + '$<IF:$<CONFIG:' + conf + '>,"' + value|string + '",' %}
                {#- {%- if loop.last %}{% set generator_expression.str = generator_expression.str + '"' + it + '-NOTFOUND"' %}{% endif %} -#}
                {%- if loop.last %}{% set generator_expression.str = generator_expression.str + '""' %}{% endif %}
            {%- endfor -%}
            {% for i in range(values|count) %}{%- set generator_expression.str = generator_expression.str + '>' %}{% endfor %}
        set({{ it }} {{ generator_expression.str }})
        {%- endfor %}

        # Adjustments that depends on the build_type
        conan_set_vs_runtime()
    """)

    def __init__(self, conanfile,
                 generator=None,
                 cmake_system_name=True,
                 parallel=True,
                 build_type=None,
                 toolset=None,
                 make_program=None,
                 msbuild_verbosity="minimal",
                 # cmake_program=None,  # TODO: cmake program should be considered in the environment
                 generator_platform=None
                 ):
        self._conanfile = conanfile
        del conanfile

        self.set_rpath = True
        self.set_std = True
        self.set_fpic = True
        self.set_libcxx = True
        self.set_find_paths = True
        self.set_find_library_paths = True
        self.set_compiler = True
        self.set_vs_runtime = True

        generator = generator or get_generator(self._conanfile.settings)
        self._context = {
            #"build_type": build_type or self._conanfile.settings.get_safe("build_type"),
            #"generator": generator,
            "generator_platform": generator_platform or
                                  get_generator_platform(self._conanfile.settings, generator),
            # "parallel": parallel,  # TODO: This is for the --build
            # '-Wno-dev'  # TODO: Can I add this to a CMake variable?
            "toolset": toolset or get_toolset(self._conanfile.settings)
        }

        builder = CMakeDefinitionsBuilder(self._conanfile,
                                          cmake_system_name=cmake_system_name,
                                          make_program=make_program, parallel=parallel,
                                          generator=generator,
                                          set_cmake_flags=False,
                                          forced_build_type=build_type,
                                          output=self._conanfile.output)
        self.definitions = Definitions()
        self.definitions.update(builder.get_definitions())

        # Build type game
        settings_build_type = self._conanfile.settings.get_safe("build_type")
        self.definitions.pop("CMAKE_BUILD_TYPE", None)
        self._context.update({"CMAKE_BUILD_TYPE": build_type or settings_build_type})

        # Some variables can go to the environment
        # TODO: Do we need this or can we move it to environment stuff
        self.environment = {}
        set_env = "pkg_config" in self._conanfile.generators and "PKG_CONFIG_PATH" not in os.environ
        if set_env:
            self.environment.update({
                "PKG_CONFIG_PATH": self._conanfile.install_folder
            })

        # self._msbuild_verbosity = os.getenv("CONAN_MSBUILD_VERBOSITY") or msbuild_verbosity  # TODO: This is for the --build

    def dump(self, install_folder):
        # The user can modify these dictionaries, add them to the context in the very last moment
        self._context.update({
            "definitions": self.definitions,
            "environment": self.environment,
            "options": {"set_rpath": self.set_rpath,
                        "set_std": self.set_std,
                        "set_fpic": self.set_fpic,
                        "set_libcxx": self.set_libcxx,
                        "set_find_paths": self.set_find_paths,
                        "set_find_library_paths": self.set_find_library_paths,
                        "set_compiler": self.set_compiler,
                        "set_vs_runtime": self.set_vs_runtime}
        })

        conan_project_include_cmake = os.path.join(install_folder, "conan_project_include.cmake")
        with open(conan_project_include_cmake, "w") as f:
            t = Template(self._template_project_include)
            content = t.render(conan_adjustements_cmake=self.conan_adjustements.replace("\\", "/"),
                               configuration_types_definitions=self.definitions.configuration_types,
                               **self._context)
            f.write(content)

        with open(os.path.join(install_folder, self.filename), "w") as f:
            # TODO: I need the profile_host and profile_build here!
            # TODO: What if the compiler is a build require?
            # TODO: Add all the stuff related to settings (ALL settings or just _MY_ settings?)
            # TODO: I would want to have here the path to the compiler too
            # compiler = "clang" if self._conanfile.settings.compiler == "apple-clang" else self._conanfile.settings.compiler
            # self._context.update({"os": self._conanfile.settings.os,
            #            "arch": self._conanfile.settings.arch,
            #            "c_compiler": compiler,
            #            "cxx_compiler": compiler+'++'})

            t = Template(self._template_toolchain)
            content = t.render(conan_adjustements_cmake=self.conan_adjustements.replace("\\", "/"),
                               conan_project_include_cmake=conan_project_include_cmake.replace("\\", "/"),
                               **self._context)

            f.write(content)

            # TODO: Remove this, intended only for testing
            f.write('\n\nset(ENV{TOOLCHAIN_ENV} "toolchain_environment")\n')
            f.write('set(TOOLCHAIN_VAR "toolchain_variable")\n')
