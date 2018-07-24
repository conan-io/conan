#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

from conans.client.runner import ConanRunner
from conans.client.tools import which
from conans.model.version import Version
from six import StringIO
import os

GCC = 'gcc'
CLANG = 'clang'
APPLE_CLANG = 'apple-clang'


class CompilerId(object):
    def __init__(self, compiler, major, minor, patch):
        # type: (str, int, int, int) -> object
        self._compiler = compiler
        self._major = major
        self._minor = minor
        self._patch = patch
        self._version = Version('%s.%s.%s' % (major, minor, patch))

    def check_settings(self, settings):
        compiler = settings.get_safe('compiler')
        compiler_version = settings.get_safe('compiler.version')
        if not compiler or not compiler_version:
            return False
        version = Version(compiler_version)
        if compiler != self._compiler:
            return False
        return self._version.compatible(version)

    @property
    def compiler(self):
        return self._compiler

    @property
    def major(self):
        return self._major

    @property
    def minor(self):
        return self._minor

    @property
    def patch(self):
        return self._patch

    def __str__(self):
        return '%s %s.%s.%s' % (self.compiler, self.major, self.minor, self.patch)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.compiler == other.compiler and \
               self.major == other.major and \
               self.minor == other.minor and \
               self.patch == other.patch

    def __ne__(self, other):
        return not self.__eq__(other)

UNKWNON_COMPILER = CompilerId(None, None, None, None)


def compiler_id(compiler, runner=None):
    try:
        from subprocess import DEVNULL
    except ImportError:
        DEVNULL = open(os.devnull, 'rb')
    runner = runner or ConanRunner()
    result = StringIO()
    command = compiler
    # -E run only preprocessor
    # -dM generate list of #define directives
    # - read input file from standard input
    command += ' -E -dM -'
    exit_code = runner(command, output=result, the_input=DEVNULL)
    if 0 != exit_code:
        return UNKWNON_COMPILER
    output = result.getvalue()
    defines = dict()
    for line in output.split('\n'):
        tokens = line.split(' ')
        if len(tokens) >= 3:
            name = tokens[1]
            value = ' '.join(tokens[2:])
            defines[name] = value
    try:
        if '__clang_major__' in defines:
            compiler = APPLE_CLANG if '__apple_build_version__' in defines else CLANG
            major = int(defines['__clang_major__'])
            minor = int(defines['__clang_minor__'])
            patch = int(defines['__clang_patchlevel__'])
        elif '__GNUC__' in defines:
            compiler = GCC
            major = int(defines['__GNUC__'])
            minor = int(defines['__GNUC_MINOR__'])
            patch = int(defines['__GNUC_PATCHLEVEL__'])
        else:
            return UNKWNON_COMPILER
    except KeyError:
        # required macro wasn't defined
        return UNKWNON_COMPILER
    except ValueError:
        # macro was defined, but wasn't parsed as an integer
        return UNKWNON_COMPILER
    return CompilerId(compiler, major, minor, patch)


def guess_compiler(settings, language):
    def compiler_name(executable):
        return '%s.exe' % executable if os.name == 'nt' else executable

    env_var = {'C': 'CC', 'C++': 'CXX'}.get(language)
    if env_var in os.environ:
        return os.environ[env_var]
    compiler = settings.get_safe('compiler')
    if compiler == 'gcc':
        name = {'C': 'gcc', 'C++': 'g++'}.get(language)
        return which(compiler_name(name))
    elif compiler == 'clang':
        name = {'C': 'clang', 'C++': 'clang++'}.get(language)
        return which(compiler_name(name))
    elif compiler == 'apple-clang':
        from conans.client.tools import XCRun
        xcrun = XCRun(settings)
        compiler = {'C': xcrun.cc, 'C++': xcrun.cxx}.get(language)
        return compiler
    else:
        return None


def guess_c_compiler(settings):
    return guess_compiler(settings, 'C')


def guess_cxx_compiler(settings):
    return guess_compiler(settings, 'C++')
