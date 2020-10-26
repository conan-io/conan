import textwrap

from conans.client.build.cmake_flags import get_generator, get_generator_platform, get_toolset, \
    is_multi_configuration
from conans.client.build.compiler_flags import architecture_flag
from conans.client.tools import cpu_count
from conans.errors import ConanException
from .base import CMakeToolchainBase


# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


class CMakeGenericToolchain(CMakeToolchainBase):
    _toolchain_tpl = textwrap.dedent("""
        {% extends 'base_toolchain' %}

        {% block before_try_compile %}
            {{ super() }}
            {% if generator_platform %}set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE){% endif %}
            {% if toolset %}set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}" CACHE STRING "" FORCE){% endif %}
        {% endblock %}

        {% block main %}
            {{ super() }}

            {% if shared_libs -%}
                message(STATUS "Conan toolchain: Setting BUILD_SHARED_LIBS= {{ shared_libs }}")
                set(BUILD_SHARED_LIBS {{ shared_libs }})
            {%- endif %}

            {% if fpic -%}
                message(STATUS "Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE=ON (options.fPIC)")
                set(CMAKE_POSITION_INDEPENDENT_CODE ON)
            {%- endif %}

            {% if skip_rpath -%}
                set(CMAKE_SKIP_RPATH 1 CACHE BOOL "rpaths" FORCE)
                # Policy CMP0068
                # We want the old behavior, in CMake >= 3.9 CMAKE_SKIP_RPATH won't affect install_name in OSX
                set(CMAKE_INSTALL_NAME_DIR "")
            {% endif -%}

            {% if parallel -%}
                set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ parallel }}")
                set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ parallel }}")
            {%- endif %}

            {% if architecture -%}
                set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ architecture }}")
                set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ architecture }}")
                set(CONAN_SHARED_LINKER_FLAGS "${CONAN_SHARED_LINKER_FLAGS} {{ architecture }}")
                set(CONAN_EXE_LINKER_FLAGS "${CONAN_EXE_LINKER_FLAGS} {{ architecture }}")
            {%- endif %}

            {% if set_libcxx -%}
                set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ set_libcxx }}")
            {%- endif %}
            {% if glibcxx -%}
                add_definitions(-D_GLIBCXX_USE_CXX11_ABI={{ glibcxx }})
            {%- endif %}

            {% if cppstd -%}
                message(STATUS "Conan C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}")
                set(CMAKE_CXX_STANDARD {{ cppstd }})
                set(CMAKE_CXX_EXTENSIONS {{ cppstd_extensions }})
            {%- endif %}

            set(CMAKE_CXX_FLAGS_INIT "${CONAN_CXX_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_C_FLAGS_INIT "${CONAN_C_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_SHARED_LINKER_FLAGS_INIT "${CONAN_SHARED_LINKER_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_EXE_LINKER_FLAGS_INIT "${CONAN_EXE_LINKER_FLAGS}" CACHE STRING "" FORCE)
        {% endblock %}
        """)

    _project_include_filename_tpl = textwrap.dedent("""
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
        super(CMakeGenericToolchain, self).__init__(conanfile)

        self.fpic = self._deduce_fpic()
        self.vs_static_runtime = self._deduce_vs_static_runtime()
        self.parallel = parallel

        self.generator = generator or get_generator(self._conanfile)
        self.generator_platform = (generator_platform or
                                   get_generator_platform(self._conanfile.settings,
                                                          self.generator))
        self.toolset = toolset or get_toolset(self._conanfile.settings, self.generator)

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

    def _get_templates(self):
        templates = super(CMakeGenericToolchain, self)._get_templates()
        templates.update({
            CMakeToolchainBase.filename: self._toolchain_tpl,
            CMakeToolchainBase.project_include_filename: self._project_include_filename_tpl
        })
        return templates

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

    def _get_template_context_data(self):
        ctxt_toolchain, ctxt_project_include = \
            super(CMakeGenericToolchain, self)._get_template_context_data()
        ctxt_toolchain.update({
            "generator_platform": self.generator_platform,
            "toolset": self.toolset,
            "fpic": self.fpic,
            "skip_rpath": self.skip_rpath,
            "set_libcxx": self.set_libcxx,
            "glibcxx": self.glibcxx,
            "parallel": self.parallel,
            "cppstd": self.cppstd,
            "cppstd_extensions": self.cppstd_extensions,
            "shared_libs": self._build_shared_libs,
            "architecture": self.architecture
        })
        ctxt_project_include.update({'vs_static_runtime': self.vs_static_runtime})
        return ctxt_toolchain, ctxt_project_include
