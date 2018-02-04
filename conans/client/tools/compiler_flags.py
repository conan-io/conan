#!/usr/bin/env python
# -*- coding: utf-8 -*-


class CompilerFlags:
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
    if str(compiler) in ['gcc', 'clang', 'sun-cc']:
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
