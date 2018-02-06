#!/usr/bin/env python
# -*- coding: utf-8 -*-

from conans.tools import unix_path


class CompilerFlags(object):
    def __init__(self, cflags=None, cxxflags=None, ldflags=None, defines=None):
        self._cflags = cflags if cflags else []
        self._cxxflags = cxxflags if cxxflags else []
        self._ldflags = ldflags if ldflags else []
        self._defines = defines if defines else []

    @property
    def cflags(self):
        return self._cflags

    @property
    def cxxflags(self):
        return self._cxxflags

    @property
    def ldflags(self):
        return self._ldflags

    @property
    def defines(self):
        return self._defines

    def append(self, additional_flags):
        """
        merges compiler flags with additional flags specified
        :param additional_flags: flags to be added
        """
        self.cflags.extend(additional_flags.cflags)
        self.cxxflags.extend(additional_flags.cxxflags)
        self.ldflags.extend(additional_flags.ldflags)
        self.defines.extend(additional_flags.defines)


def architecture_flags(compiler=None, arch=None):
    """
    returns flags specific to the target architecture and compiler
    """
    if str(compiler) in ['gcc', 'apple-clang', 'clang', 'sun-cc']:
        if str(arch) in ['x86_64', 'sparcv9']:
            return CompilerFlags(cflags=['-m64'], cxxflags=['-m64'], ldflags=['-m64'])
        elif str(arch) in ['x86', 'sparc']:
            return CompilerFlags(cflags=['-m32'], cxxflags=['-m32'], ldflags=['-m32'])
    return CompilerFlags()


def libcxx_flags(compiler=None, libcxx=None):
    """
    returns flags specific to the target C++ standard library
    """
    flags = CompilerFlags()
    if str(compiler) in ['gcc', 'clang', 'apple-clang']:
        if str(libcxx) == 'libstdc++':
            flags.defines.append('_GLIBCXX_USE_CXX11_ABI=0')
        elif str(libcxx) == 'libstdc++11':
            flags.defines.append('_GLIBCXX_USE_CXX11_ABI=1')
    if str(compiler) in ['clang', 'apple-clang']:
        if str(libcxx) in ['libstdc++', 'libstdc++11']:
            flags.cxxflags.append('-stdlib=libstdc++')
        elif str(libcxx) == 'libc++':
            flags.cxxflags.append('-stdlib=libc++')
    elif str(compiler) == 'sun-cc':
        flags.cxxflags.append({"libCstd": "-library=Cstd",
                               "libstdcxx": "-library=stdcxx4",
                               "libstlport": "-library=stlport4",
                               "libstdc++": "-library=stdcpp"}.get(libcxx, None))
    return flags


def pic_flags(compiler=None):
    """
    returns PIC (position independent code) flags, such as -fPIC
    """
    if compiler == 'Visual Studio':
        return CompilerFlags()
    return CompilerFlags(cflags=['-fPIC'], cxxflags=['-fPIC'])


def build_type_flags(compiler=None, build_type=None):
    """
    returns flags specific to the build type (Debug, Release, etc.)
    usually definitions like DEBUG, _DEBUG, NDEBUG, or flags to
    control debug information (-s, -g, /Zi, etc.)
    """
    flags = CompilerFlags()
    if str(compiler) == 'Visual Studio':
        if build_type == 'Debug':
            flags.cflags.append('/Zi')
            flags.cxxflags.append('/Zi')
    else:
        if build_type == 'Debug':
            flags.cflags.append('-g')
            flags.cxxflags.append('-g')
        elif build_type == 'Release' and str(compiler) == 'gcc':
            flags.cflags.append('-s')
            flags.cxxflags.append('-s')
            # TODO: why NDEBUG only for GCC?
            flags.defines.append('NDEBUG')
    return flags


def adjust_path(path, win_bash=False, subsystem=None, compiler=None):
    """
    adjusts path to be safely passed to the compiler command line
    for Windows bash, ensures path is in format according to the subsystem
    for path with spaces, places double quotes around it
    converts slashes to backslashes, or vice versa
    """
    if str(compiler) == 'Visual Studio':
        path = path.replace('/', '\\')
    else:
        path = path.replace('\\', '/')
    if win_bash:
        path = unix_path(path, subsystem)
    return '"%s"' % path if ' ' in path else path


def sysroot_flags(sysroot, win_bash=False, subsystem=None, compiler=None):
    if str(compiler) != 'Visual Studio' and sysroot:
        sysroot = adjust_path(sysroot, win_bash=win_bash, subsystem=subsystem, compiler=compiler)
        sysroot_flag = ['--sysroot=%s' % sysroot]
        return CompilerFlags(cflags=sysroot_flag, cxxflags=sysroot_flag, ldflags=sysroot_flag)
    return CompilerFlags()


def format_defines(defines):
    return ["-D%s" % define for define in defines]


def format_include_paths(include_paths, win_bash=False, subsystem=None, compiler=None):
    return ["-I%s" % adjust_path(include_path, win_bash=win_bash, subsystem=subsystem, compiler=compiler)
            for include_path in include_paths]


def format_library_paths(library_paths, win_bash=False, subsystem=None, compiler=None):
    pattern = "-LIBPATH:%s" if str(compiler) == 'Visual Studio' else "-L%s"
    return [pattern % adjust_path(library_path, win_bash=win_bash, subsystem=subsystem, compiler=compiler)
            for library_path in library_paths]


def format_libraries(libraries, compiler=None):
    pattern = "%s" if str(compiler) == 'Visual Studio' else "-l%s"
    return [pattern % library for library in libraries]
