import os
import re
import textwrap

from jinja2 import Template

from conan.tools._compilers import architecture_flag
from conans.client.tools import cpu_count
from conans.util.files import load
from conans.errors import ConanException
from conan.tools.cmake.base import CMakeToolchainBase
from conan.tools.cmake.utils import get_generator, is_multi_configuration


# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


def get_toolset(settings, generator):
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    if compiler == "Visual Studio":
        subs_toolset = settings.get_safe("compiler.toolset")
        if subs_toolset:
            return subs_toolset
    elif compiler == "intel" and compiler_base == "Visual Studio" and "Visual" in generator:
        compiler_version = settings.get_safe("compiler.version")
        if compiler_version:
            compiler_version = compiler_version if "." in compiler_version else \
                "%s.0" % compiler_version
            return "Intel C++ Compiler " + compiler_version
    return None


def get_generator_platform(settings, generator):
    # Returns the generator platform to be used by CMake
    if "CONAN_CMAKE_GENERATOR_PLATFORM" in os.environ:
        return os.environ["CONAN_CMAKE_GENERATOR_PLATFORM"]

    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    arch = settings.get_safe("arch")

    if settings.get_safe("os") == "WindowsCE":
        return settings.get_safe("os.platform")

    if (compiler in ("Visual Studio", "msvc") or compiler_base == "Visual Studio") and \
            generator and "Visual" in generator:
        return {"x86": "Win32",
                "x86_64": "x64",
                "armv7": "ARM",
                "armv8": "ARM64"}.get(arch)
    return None


class Block:
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def get_block(self):
        context = self.context()
        if not context:
            return
        return Template(self.template, trim_blocks=True, lstrip_blocks=True).render(**context)

    def context(self):
        raise NotImplementedError()

    @property
    def template(self):
        raise NotImplementedError()


class VSRuntimeBlock(Block):
    template = textwrap.dedent("""
        # Definition of VS runtime, defined from build_type, compiler.runtime, compiler.runtime_type
        {% set genexpr = namespace(str='') %}
        {% for config, value in vs_runtimes.items() %}
            {% set genexpr.str = genexpr.str +
                                  '$<$<CONFIG:' + config + '>:' + value|string + '>' %}
        {% endfor %}
        set(CMAKE_MSVC_RUNTIME_LIBRARY "{{ genexpr.str }}")
        """)

    def context(self):
        # Parsing existing toolchain file to get existing configured runtimes
        settings = self._conanfile.settings
        compiler = settings.get_safe("compiler")
        if compiler not in ("Visual Studio", "msvc"):
            return

        config_dict = {}
        if os.path.exists(CMakeToolchainBase.filename):
            existing_include = load(CMakeToolchainBase.filename)
            msvc_runtime_value = re.search(r"set\(CMAKE_MSVC_RUNTIME_LIBRARY \"([^)]*)\"\)",
                                           existing_include)
            if msvc_runtime_value:
                capture = msvc_runtime_value.group(1)
                matches = re.findall(r"\$<\$<CONFIG:([A-Za-z]*)>:([A-Za-z]*)>", capture)
                config_dict = dict(matches)

        build_type = settings.get_safe("build_type")  # FIXME: change for configuration
        runtime = settings.get_safe("compiler.runtime")
        if compiler == "Visual Studio":
            config_dict[build_type] = {"MT": "MultiThreaded",
                                       "MTd": "MultiThreadedDebug",
                                       "MD": "MultiThreadedDLL",
                                       "MDd": "MultiThreadedDebugDLL"}[runtime]
        if compiler == "msvc":
            runtime_type = settings.get_safe("compiler.runtime_type")
            rt = "MultiThreadedDebug" if runtime_type == "Debug" else "MultiThreaded"
            if runtime != "static":
                rt += "DLL"
            config_dict[build_type] = rt
        return {"vs_runtimes": config_dict}


class FPicBlock(Block):
    template = textwrap.dedent("""
        {% if fpic %}
        message(STATUS "Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE=ON (options.fPIC)")
        set(CMAKE_POSITION_INDEPENDENT_CODE ON)
        {% endif %}
        """)

    def context(self):
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
        return {"fpic": fpic}


class GLibCXXBlock(Block):
    template = textwrap.dedent("""
        {% if set_libcxx %}
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ set_libcxx }}")
        {% endif %}
        {% if glibcxx %}
        add_definitions(-D_GLIBCXX_USE_CXX11_ABI={{ glibcxx }})
        {% endif %}
        """)

    def context(self):
        libcxx = self._conanfile.settings.get_safe("compiler.libcxx")
        if not libcxx:
            return None
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
        return {"lib": lib, "glib": glib}


class SkipRPath(Block):
    template = textwrap.dedent("""
        set(CMAKE_SKIP_RPATH 1 CACHE BOOL "rpaths" FORCE)
        # Policy CMP0068
        # We want the old behavior, in CMake >= 3.9 CMAKE_SKIP_RPATH won't affect install_name in OSX
        set(CMAKE_INSTALL_NAME_DIR "")
        """)

    def context(self):
        if self._conanfile.settings.get_safe("os") != "Macos":
            return
        return {"skip_rpath": True}


class ArchitectureBlock(Block):
    template = textwrap.dedent("""
        {% if arch_flag %}
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ arch_flag }}")
        set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ arch_flag }}")
        set(CONAN_SHARED_LINKER_FLAGS "${CONAN_SHARED_LINKER_FLAGS} {{ arch_flag }}")
        set(CONAN_EXE_LINKER_FLAGS "${CONAN_EXE_LINKER_FLAGS} {{ arch_flag }}")
        {% endif %}
        """)

    def context(self):
        arch_flag = architecture_flag(self._conanfile.settings)
        if not arch_flag:
            return
        return {"arch_flag": arch_flag}


class CMakeGenericToolchain(CMakeToolchainBase):
    _toolchain_tpl = textwrap.dedent("""
        {% extends 'base_toolchain' %}

        {% block before_try_compile %}
        {{ super() }}
        {% if generator_platform %}set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE){% endif %}
        {% if toolset %}set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}" CACHE STRING "" FORCE){% endif %}
        {% if compiler %}
        set(CMAKE_C_COMPILER {{ compiler }})
        set(CMAKE_CXX_COMPILER {{ compiler }})
        {%- endif %}
        {% endblock %}

        {% block main %}
            {{ super() }}

            {% for conan_block in conan_main_blocks %}
            {{ conan_block }}
            {% endfor %}
        {% endblock %}
        """)

    def __init__(self, conanfile, generator=None, generator_platform=None, build_type=None,
                 toolset=None, parallel=True):
        super(CMakeGenericToolchain, self).__init__(conanfile)

        self.conan_main_blocks = [FPicBlock, SkipRPath, GLibCXXBlock, ArchitectureBlock,
                                  VSRuntimeBlock]

        self.parallel = parallel

        self.generator = generator or get_generator(self._conanfile)
        self.generator_platform = (generator_platform or
                                   get_generator_platform(self._conanfile.settings,
                                                          self.generator))
        self.toolset = toolset or get_toolset(self._conanfile.settings, self.generator)
        if (self.generator is not None and "Ninja" in self.generator
                and "Visual" in self._conanfile.settings.compiler):
            self.compiler = "cl"
        else:
            self.compiler = None  # compiler defined by default

        try:
            self._build_shared_libs = "ON" if self._conanfile.options.shared else "OFF"
        except ConanException:
            self._build_shared_libs = None

        self.parallel = None
        if parallel:
            if self.generator and "Visual Studio" in self.generator:
                self.parallel = "/MP%s" % cpu_count(output=self._conanfile.output)

        self.cppstd, self.cppstd_extensions = self._cppstd()

        # TODO: I would want to have here the path to the compiler too
        build_type = build_type or self._conanfile.settings.get_safe("build_type")
        self.build_type = build_type if not is_multi_configuration(self.generator) else None

    def _get_templates(self):
        templates = super(CMakeGenericToolchain, self)._get_templates()
        templates.update({
            CMakeToolchainBase.filename: self._toolchain_tpl
        })
        return templates

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
        conan_main_blocks = []
        for b in self.conan_main_blocks:
            block = b(self._conanfile).get_block()
            if block:
                conan_main_blocks.append(block)

        ctxt_toolchain = super(CMakeGenericToolchain, self)._get_template_context_data()
        ctxt_toolchain.update({
            "generator_platform": self.generator_platform,
            "toolset": self.toolset,
            "parallel": self.parallel,
            "cppstd": self.cppstd,
            "cppstd_extensions": self.cppstd_extensions,
            "shared_libs": self._build_shared_libs,
            "compiler": self.compiler,
            "conan_main_blocks": conan_main_blocks
        })
        return ctxt_toolchain
