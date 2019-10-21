# coding=utf-8

import os
import textwrap
from jinja2 import Template

from conans.client.build.cmake_flags import get_generator, get_generator_platform, CMakeDefinitionsBuilder, get_toolset


# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


class CMakeToolchain:
    filename = "conan_toolchain.cmake"
    conan_adjustements = os.path.join(os.path.dirname(__file__), "conan_adjustments.cmake")

    _template = textwrap.dedent("""
        # Conan generated toolchain file
        
        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        if(CONAN_TOOLCHAIN_INCLUDED)
          return()
        endif()
        set(CONAN_TOOLCHAIN_INCLUDED true)

        message("Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")
        
        # CMAKE_BUILD_TYPE: Use it only if it isn't a multi-config generator
        get_property(_GENERATOR_IS_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG )
        if(NOT _GENERATOR_IS_MULTI_CONFIG)
            set(CMAKE_BUILD_TYPE "{{ CMAKE_BUILD_TYPE }}" CACHE STRING "Choose the type of build." FORCE)
        endif()
        unset(_GENERATOR_IS_MULTI_CONFIG)

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
        
        
        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(NOT _CMAKE_IN_TRY_COMPILE)
            message(">>>> NOT TRY COMPILE")
            include("{{conan_adjustements_cmake}}")
            
            # We need to reset these values because Conan is appending to them
            set(CMAKE_CXX_FLAGS "")
            set(CMAKE_CXX_FLAGS_DEBUG "")
            set(CMAKE_CXX_FLAGS_RELEASE "")
            set(CMAKE_C_FLAGS "")
            set(CMAKE_C_FLAGS_DEBUG "")
            set(CMAKE_C_FLAGS_RELEASE "")
            set(CMAKE_SHARED_LINKER_FLAGS "")
            set(CMAKE_EXE_LINKER_FLAGS "")

            # We are going to adjust automagically many things as requested by Conan
            #   these are the things done by 'conan_basic_setup()'
            
            conan_set_flags("")
            conan_set_flags("_RELEASE")
            conan_set_flags("_DEBUG")
            # TODO: Do we want to set flags here if we are going to use targets? Maybe these flags are defined inside the 'toolchain' method of the recipe
            
            conan_set_rpath()
            conan_set_std()
            conan_set_fpic()
            
            #conan_check_compiler()
            conan_set_libcxx()
            conan_set_vs_runtime()
            conan_set_find_paths()
            conan_set_find_library_paths()
            
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}" CACHE STRING "" FORCE)
        else()
            # message(">>>> TRY COMPILE")
        endif()

        {#
        # Host machine        
        set(CMAKE_SYSTEM_NAME {{host.os}})
        set(CMAKE_SYSTEM_VERSION {{host.os_version}})
        set(CMAKE_SYSTEM_PROCESSOR {{host.arch}})

        # Build machine (only if different)
        set(CMAKE_HOST_SYSTEM_NAME {{build.os}})
        set(CMAKE_HOST_SYSTEM_VERSION {{build.os_version}})
        set(CMAKE_HOST_SYSTEM_PROCESSOR {{build.arch}})
        
        set(CMAKE_C_COMPILER {{c_compiler}})
        set(CMAKE_CXX_COMPILER {{cxx_compiler}})
        #}
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

        generator = generator or get_generator(self._conanfile.settings)
        self._context = {
            "conan_adjustements_cmake": self.conan_adjustements.replace("\\", "/"),
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
        self.definitions = builder.get_definitions()
        build_type = self.definitions.pop('CMAKE_BUILD_TYPE', None)
        if build_type:
            self._context.update({
                "CMAKE_BUILD_TYPE": build_type
            })

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
            "environment": self.environment
        })

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

            t = Template(self._template)
            content = t.render(**self._context)

            f.write(content)

            # TODO: Remove this, intended only for testing
            f.write('set(ENV{TOOLCHAIN_ENV} "toolchain_environment")\n')
            f.write('set(TOOLCHAIN_VAR "toolchain_variable")\n')
