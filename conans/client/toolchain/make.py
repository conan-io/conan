# coding=utf-8

import os
import platform
import textwrap

from jinja2 import Template

from conans.client.build.cppstd_flags import cppstd_from_settings, cppstd_flag_new as cppstd_flag
from conans.client.tools.oss import cross_building, \
    detected_architecture, detected_os, get_gnu_triplet, get_target_os_arch, get_build_os_arch
from conans.errors import ConanException
from conans.util.files import save


class MakeToolchain(object):
    filename = "conan_toolchain.mak"

    _template_toolchain = textwrap.dedent("""
        # Conan generated toolchain file
        ifndef CONAN_TOOLCHAIN_INCLUDED
            CONAN_TOOLCHAIN_INCLUDED = TRUE
            CONAN_TC_BUILD_TYPE = {{build_type}}
            CONAN_TC_OS_HOST = {{os_host}}
            CONAN_TC_ARCH_HOST = {{arch_host}}
            CONAN_TC_TRIPLET_HOST = {{triplet_host}}
            CONAN_TC_OS_BUILD = {{os_build}}
            CONAN_TC_ARCH_BUILD = {{arch_build}}
            CONAN_TC_TRIPLET_BUILD = {{triplet_build}}
            CONAN_TC_OS_TARGET = {{os_target}}
            CONAN_TC_ARCH_TARGET = {{arch_target}}
            CONAN_TC_TRIPLET_TARGET = {{triplet_target}}
            CONAN_TC_COMPILER = {{compiler}}
            CONAN_TC_COMPILER_VERSION = {{compiler_version}}
            CONAN_TC_COMPILER_RUNTIME = {{compiler_runtime}}
            CONAN_TC_LIBCXX = {{libcxx}}
            CONAN_TC_DEFINES = {{defines}}

            CONAN_TC_SET_LIBCXX = {{set_libcxx}}
            CONAN_TC_SET_FPIC = {{set_fpic}}

            ifeq ($(CONAN_TC_SET_LIBCXX),True)
                CONAN_TC_CLANG_BASED := $(if $(filter $(CONAN_TC_COMPILER),clang apple-clang),true)
                ifeq ($(CONAN_TC_CLANG_BASED),True)
                    CONAN_TC_LIBSTDCXX_BASED := $(if $(filter $(CONAN_TC_LIBCXX),libstdc++ libstdc++11),true)
                    ifeq ($(CONAN_TC_LIBSTDCXX_BASED),True)
                        CONAN_TC_CXXFLAGS += -stdlib=libstdc++
                    else ifeq ($(CONAN_TC_LIBCXX),libc++)
                        CONAN_TC_CXXFLAGS += -stdlib=libc++
                    endif
                else ifeq ($(CONAN_TC_COMPILER),sun-cc)
                    ifeq ($(CONAN_TC_LIBCXX),libCstd)
                        CONAN_TC_CXXFLAGS += -library=Cstd++
                    else ifeq ($(CONAN_TC_LIBCXX),libstdcxx)
                        CONAN_TC_CXXFLAGS += -library=stdcxx4
                    else ifeq ($(CONAN_TC_LIBCXX),libstlport)
                        CONAN_TC_CXXFLAGS += -library=stlport4
                    else ifeq ($(CONAN_TC_LIBCXX),libstdc++)
                        CONAN_TC_CXXFLAGS += -library=stdcpp
                    endif
                endif
                ifeq ($(CONAN_TC_LIBCXX),libstdc++11)
                    CONAN_TC_DEFINES += GLIBCXX_USE_CXX11_ABI=1
                else ifeq ($(CONAN_TC_LIBCXX),libstdc++)
                    CONAN_TC_DEFINES += GLIBCXX_USE_CXX11_ABI=0
                endif
            endif
            ifeq ($(CONAN_TC_BUILD_TYPE),Release)
                CONAN_TC_DEFINES += NDEBUG
            endif
            ifeq ($(CONAN_TC_SET_FPIC),True)
                CONAN_TC_CFLAGS += -fPIC
                CONAN_TC_CXXFLAGS += -fPIC
                CONAN_TC_SHARED_LINKER_FLAGS += -fPIC
            endif

        endif

    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile

        self._set_fpic = self._deduce_fpic()
        self._set_libcxx = True

        self._compiler = conanfile.settings.get_safe("compiler")
        self._compiler_version = conanfile.settings.get_safe("compiler.version")
        self._compiler_runtime = conanfile.settings.get_safe("compiler.runtime")
        self._libcxx = conanfile.settings.get_safe("compiler.libcxx")

        # cpp standard
        self._cppstd = cppstd_from_settings(conanfile.settings)
        self.cppstd_flag = cppstd_flag(conanfile.settings)

        self._os_host = conanfile.settings.get_safe("os")
        self._arch_host = conanfile.settings.get_safe("arch")
        self._os_target, self._arch_target = get_target_os_arch(conanfile)
        self._arch_build, self._os_build = self._get_build_os_arch()
        self._build_type = conanfile.settings.get_safe("build_type")
        # Precalculate build, host, target triplets
        self._trip_build, self._trip_host, self._trip_target = self._get_host_build_target_flags()

        self.definitions = {}

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

    def _get_host_build_target_flags(self):
        """Based on google search for build/host triplets, it could need a lot
        and complex verification"""

        if self._os_target and self._arch_target:
            try:
                target = get_gnu_triplet(self._os_target, self._arch_target, self._compiler)
            except ConanException as exc:
                self._conanfile.output.warn(str(exc))
                target = None
        else:
            target = None

        if self._os_build is None or self._arch_build is None or self._arch_host is None or self._os_host is None:
            return False, False, target

        if not cross_building(self._conanfile, self._os_build, self._arch_build):
            return False, False, target

        try:
            build = get_gnu_triplet(self._os_build, self._arch_build, self._compiler)
        except ConanException as exc:
            self._conanfile.output.warn(str(exc))
            build = None
        try:
            host = get_gnu_triplet(self._os_host, self._arch_host, self._compiler)
        except ConanException as exc:
            self._conanfile.output.warn(str(exc))
            host = None
        return build, host, target

    def _get_build_os_arch(self):
        if hasattr(self._conanfile, 'settings_build'):
            os_build, arch_build = get_build_os_arch(self._conanfile)
        else:
            # FIXME: Why not use 'os_build' and 'arch_build' from conanfile.settings?
            os_build = detected_os() or platform.system()
            arch_build = detected_architecture() or platform.machine()
        return arch_build, os_build

    def write_toolchain_files(self):

        defines = []

        for k, v in self.definitions.items():
            defines.append('%s=\\"%s\\"' % (k, v) if v is not None else k)

        context = {
            "build_type": self._build_type,
            "os_host": self._os_host,
            "arch_host": self._arch_host,
            "triplet_host": self._trip_host,
            "os_build": self._os_build,
            "arch_build": self._arch_build,
            "triplet_build": self._trip_build,
            "os_target": self._os_target,
            "arch_target": self._arch_target,
            "triplet_target": self._trip_target,
            "compiler": self._compiler,
            "compiler_version": self._compiler_version,
            "compiler_runtime": self._compiler_runtime,
            "libcxx": self._libcxx,
            "set_fpic": self._set_fpic,
            "set_libcxx": self._set_libcxx,
            "defines": " ".join(defines),
        }
        t = Template(self._template_toolchain)
        content = t.render(**context)
        print(content)
        save(self.filename, content)
