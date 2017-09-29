#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess

_global_output = None


def cmd_output(command):
    return subprocess.check_output(command).decode().strip()


class PkgConfig(object):

    def __init__(self, library, pkg_config_executable='pkg-config', static=False, msvc_syntax=False, variables=None):
        """
        :param library: library (package) name, such as libastral
        :param pkg_config_executable: specify custom pkg-config executable (e.g. for cross-compilation)
        :param static: output libraries suitable for static linking (adds --static to pkg-config command line)
        :param msvc_syntax: MSVC compatibility (adds --msvc-syntax to pkg-config command line)
        :param variables: dictionary of pkg-config variables (passed as --define-variable=VARIABLENAME=VARIABLEVALUE)
        """
        self.library = library
        self.pkg_config_executable = pkg_config_executable
        self.static = static
        self.msvc_syntax = msvc_syntax
        self.define_variables = variables

        variable_names = self._parse_output('print-variables').split()
        self._variables = dict()
        for name in variable_names:
            self.variables[name] = self._parse_output('variable=%s' % name)

        self.info = dict()
        for option in ['cflags', 'cflags-only-I', 'cflags-only-other',
                       'libs', 'libs-only-L', 'libs-only-l', 'libs-only-other',
                       'print-provides', 'print-requires', 'print-requires-private']:
            self.info[option] = self._parse_output(option).split()

    def _parse_output(self, option):
        command = [self.pkg_config_executable, '--' + option, self.library]
        if self.static:
            command.append('--static')
        if self.msvc_syntax:
            command.append('--msvc-syntax')
        if self.define_variables:
            for name, value in self.define_variables:
                command.append('--definevariable=%s=%s' % (name, value))
        return cmd_output(command)

    @property
    def cflags(self):
        return self.info['cflags']

    @property
    def cflags_only_I(self):
        return self.info['cflags-only-I']

    @property
    def cflags_only_other(self):
        return self.info['cflags-only-other']

    @property
    def libs(self):
        return self.info['libs']

    @property
    def libs_only_L(self):
        return self.info['libs-only-L']

    @property
    def libs_only_l(self):
        return self.info['libs-only-l']

    @property
    def libs_only_other(self):
        return self.info['libs-only-other']

    @property
    def provides(self):
        return self.info['print-provides']

    @property
    def requires(self):
        return self.info['print-requires']

    @property
    def requires_private(self):
        return self.info['print-requires-private']

    @property
    def variables(self):
        return self._variables
