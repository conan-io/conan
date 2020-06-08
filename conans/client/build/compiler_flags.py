#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    # Visual Studio cl options reference:
    #   https://msdn.microsoft.com/en-us/library/610ecb4h.aspx
    #       "Options are specified by either a forward slash (/) or a dash (–)."
    #   Here we use "-" better than "/" that produces invalid escaped chars using AutoTools.
    #   -LIBPATH, -D, -I, -ZI and so on.

"""

from conans.client.tools.apple import is_apple_os
from conans.client.tools.oss import cpu_count
from conans.client.tools.win import unix_path


GCC_LIKE = ['clang', 'apple-clang', 'gcc']


def _base_compiler(settings):
    return settings.get_safe("compiler.base") or settings.get_safe("compiler")


# FIXME : pass conanfile instead of settings and os_build
def rpath_flags(settings, os_build, lib_paths):
    compiler = _base_compiler(settings)
    if not os_build:
        return []
    if compiler in GCC_LIKE:
        rpath_separator = "," if is_apple_os(os_build) else "="
        return ['-Wl,-rpath%s"%s"' % (rpath_separator, x.replace("\\", "/"))
                for x in lib_paths if x]
    return []


def architecture_flag(settings):
    """
    returns flags specific to the target architecture and compiler
    """
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    arch = settings.get_safe("arch")
    the_os = settings.get_safe("os")
    if not compiler or not arch:
        return ""

    if str(compiler) in ['gcc', 'apple-clang', 'clang', 'sun-cc']:
        if str(arch) in ['x86_64', 'sparcv9', 's390x']:
            return '-m64'
        elif str(arch) in ['x86', 'sparc']:
            return '-m32'
        elif str(arch) in ['s390']:
            return '-m31'
        elif str(the_os) == 'AIX':
            if str(arch) in ['ppc32']:
                return '-maix32'
            elif str(arch) in ['ppc64']:
                return '-maix64'
    elif str(compiler) == "intel":
        # https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-m32-m64-qm32-qm64
        if str(arch) == "x86":
            return "/Qm32" if str(compiler_base) == "Visual Studio" else "-m32"
        elif str(arch) == "x86_64":
            return "/Qm64" if str(compiler_base) == "Visual Studio" else "-m64"
    return ""


def libcxx_define(settings):
    compiler = _base_compiler(settings)
    libcxx = settings.get_safe("compiler.libcxx")
    if not compiler or not libcxx:
        return ""

    if str(compiler) in GCC_LIKE:
        if str(libcxx) == 'libstdc++':
            return '_GLIBCXX_USE_CXX11_ABI=0'
        elif str(libcxx) == 'libstdc++11':
            return '_GLIBCXX_USE_CXX11_ABI=1'
    return ""


def libcxx_flag(settings):
    """
    returns flag specific to the target C++ standard library
    """
    compiler = _base_compiler(settings)
    libcxx = settings.get_safe("compiler.libcxx")
    if not compiler or not libcxx:
        return ""
    if str(compiler) in ['clang', 'apple-clang']:
        if str(libcxx) in ['libstdc++', 'libstdc++11']:
            return '-stdlib=libstdc++'
        elif str(libcxx) == 'libc++':
            return '-stdlib=libc++'
    elif str(compiler) == 'sun-cc':
        return ({"libCstd": "-library=Cstd",
                            "libstdcxx": "-library=stdcxx4",
                            "libstlport": "-library=stlport4",
                            "libstdc++": "-library=stdcpp"}.get(libcxx, ""))
    elif str(compiler) == "qcc":
        return "-Y _%s" % str(libcxx)
    return ""


def pic_flag(settings):
    """
    returns PIC (position independent code) flags, such as -fPIC
    """
    compiler = _base_compiler(settings)
    if not compiler or compiler == 'Visual Studio':
        return ""
    return '-fPIC'


def build_type_flags(settings):
    """
    returns flags specific to the build type (Debug, Release, etc.)
    (-s, -g, /Zi, etc.)
    """
    compiler = _base_compiler(settings)
    build_type = settings.get_safe("build_type")
    vs_toolset = settings.get_safe("compiler.toolset")
    if not compiler or not build_type:
        return ""

    # https://github.com/Kitware/CMake/blob/d7af8a34b67026feaee558433db3a835d6007e06/
    # Modules/Platform/Windows-MSVC.cmake
    if str(compiler) == 'Visual Studio':
        if vs_toolset and "clang" in str(vs_toolset):
            flags = {"Debug": ["-gline-tables-only", "-fno-inline", "-O0"],
                     "Release": ["-O2"],
                     "RelWithDebInfo": ["-gline-tables-only", "-O2", "-fno-inline"],
                     "MinSizeRel": []
                     }.get(build_type, ["-O2", "-Ob2"])
        else:
            flags = {"Debug": ["-Zi", "-Ob0", "-Od"],
                     "Release": ["-O2", "-Ob2"],
                     "RelWithDebInfo": ["-Zi", "-O2", "-Ob1"],
                     "MinSizeRel": ["-O1", "-Ob1"],
                     }.get(build_type, [])
        return flags
    else:
        # https://github.com/Kitware/CMake/blob/f3bbb37b253a1f4a26809d6f132b3996aa2e16fc/
        # Modules/Compiler/GNU.cmake
        # clang include the gnu (overriding some things, but not build type) and apple clang
        # overrides clang but it doesn't touch clang either
        if str(compiler) in ["clang", "gcc", "apple-clang", "qcc"]:
            # FIXME: It is not clear that the "-s" is something related with the build type
            # cmake is not adjusting it
            # -s: Remove all symbol table and relocation information from the executable.
            flags = {"Debug": ["-g"],
                     "Release": ["-O3", "-s"] if str(compiler) == "gcc" else ["-O3"],
                     "RelWithDebInfo": ["-O2", "-g"],
                     "MinSizeRel": ["-Os"],
                     }.get(build_type, [])
            return flags
        elif str(compiler) == "sun-cc":
            # https://github.com/Kitware/CMake/blob/f3bbb37b253a1f4a26809d6f132b3996aa2e16fc/
            # Modules/Compiler/SunPro-CXX.cmake
            flags = {"Debug": ["-g"],
                     "Release": ["-xO3"],
                     "RelWithDebInfo": ["-xO2", "-g"],
                     "MinSizeRel": ["-xO2", "-xspace"],
                     }.get(build_type, [])
            return flags
    return ""


def build_type_define(build_type=None):
    """
    returns definitions specific to the build type (Debug, Release, etc.)
    like DEBUG, _DEBUG, NDEBUG
    """
    return 'NDEBUG' if build_type in ['Release', 'RelWithDebInfo', 'MinSizeRel'] else ""


def adjust_path(path, settings, win_bash=False, subsystem=None):
    """
    adjusts path to be safely passed to the compiler command line
    for Windows bash, ensures path is in format according to the subsystem
    for path with spaces, places double quotes around it
    converts slashes to backslashes, or vice versa
    """
    compiler = _base_compiler(settings)
    if str(compiler) == 'Visual Studio':
        path = path.replace('/', '\\')
    else:
        path = path.replace('\\', '/')
    if win_bash:
        path = unix_path(path, subsystem)
    return '"%s"' % path if ' ' in path else path


def sysroot_flag(sysroot, settings, win_bash=False, subsystem=None):
    compiler = _base_compiler(settings)
    if str(compiler) != 'Visual Studio' and sysroot:
        sysroot = adjust_path(sysroot, settings, win_bash=win_bash, subsystem=subsystem)
        return '--sysroot=%s' % sysroot
    return ""


def visual_runtime(runtime):
    if runtime:
        return "-%s" % runtime
    return ""


def format_defines(defines):
    return ["-D%s" % define for define in defines if define]


include_path_option = "-I"
visual_linker_option_separator = "-link"  # Further options will apply to the linker


def format_include_paths(include_paths, settings, win_bash=False, subsystem=None):
    return ["%s%s" % (include_path_option, adjust_path(include_path, settings, win_bash=win_bash,
                                                       subsystem=subsystem))
            for include_path in include_paths if include_path]


def format_library_paths(library_paths, settings, win_bash=False, subsystem=None):
    compiler = _base_compiler(settings)
    pattern = "-LIBPATH:%s" if str(compiler) == 'Visual Studio' else "-L%s"
    return [pattern % adjust_path(library_path, settings, win_bash=win_bash,
                                  subsystem=subsystem)
            for library_path in library_paths if library_path]


def format_libraries(libraries, settings):
    result = []
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    for library in libraries:
        if str(compiler) == 'Visual Studio' or str(compiler_base) == 'Visual Studio':
            if not library.endswith(".lib"):
                library += ".lib"
            result.append(library)
        else:
            result.append("-l%s" % library)
    return result


def parallel_compiler_cl_flag(output=None):
    return "/MP%s" % cpu_count(output=output)


def format_frameworks(frameworks, settings):
    """
    returns an appropriate compiler flags to link with Apple Frameworks
    or an empty array, if Apple Frameworks aren't supported by the given compiler
    """
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    if (str(compiler) not in GCC_LIKE) and (str(compiler_base) not in GCC_LIKE):
        return []
    return ["-framework %s" % framework for framework in frameworks]


def format_framework_paths(framework_paths, settings):
    """
    returns an appropriate compiler flags to specify Apple Frameworks search paths
    or an empty array, if Apple Frameworks aren't supported by the given compiler
    """
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    if (str(compiler) not in GCC_LIKE) and (str(compiler_base) not in GCC_LIKE):
        return []
    return ["-F %s" % adjust_path(framework_path, settings) for framework_path in framework_paths]
