#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
from conans.errors import ConanException


class PkgConfig(object):
    @staticmethod
    def _cmd_output(command):
        return subprocess.check_output(command).decode().strip()

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

        self._variables = dict()
        self.info = dict()

    def _parse_output(self, option):
        command = [self.pkg_config_executable, '--' + option, self.library]
        if self.static:
            command.append('--static')
        if self.msvc_syntax:
            command.append('--msvc-syntax')
        if self.define_variables:
            for name, value in self.define_variables.items():
                command.append('--define-variable=%s=%s' % (name, value))
        try:
            return self._cmd_output(command)
        except subprocess.CalledProcessError as e:
            raise ConanException('pkg-config command %s failed with error: %s' % (command, e))

    def _get_option(self, option):
        if option not in self.info:
            self.info[option] = self._parse_output(option).split()
        return self.info[option]

    @property
    def cflags(self):
        return self._get_option('cflags')

    @property
    def cflags_only_I(self):
        return self._get_option('cflags-only-I')

    @property
    def cflags_only_other(self):
        return self._get_option('cflags-only-other')

    @property
    def libs(self):
        return self._get_option('libs')

    @property
    def libs_only_L(self):
        return self._get_option('libs-only-L')

    @property
    def libs_only_l(self):
        return self._get_option('libs-only-l')

    @property
    def libs_only_other(self):
        return self._get_option('libs-only-other')

    @property
    def provides(self):
        return self._get_option('print-provides')

    @property
    def requires(self):
        return self._get_option('print-requires')

    @property
    def requires_private(self):
        return self._get_option('print-requires-private')

    @property
    def variables(self):
        if not self._variables:
            variable_names = self._parse_output('print-variables').split()
            for name in variable_names:
                self._variables[name] = self._parse_output('variable=%s' % name)
        return self._variables
