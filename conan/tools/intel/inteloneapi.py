#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Intel generator module for oneAPI Toolkits.

    For simplicity and clarity, Intel informally refers to some of the terms in this document,
    as listed below:

        - ICX - Intel oneAPI DPC++/C++ Compiler
        - ICC Classic - Intel C++ Compiler Classic
        - DPCPP - Intel oneAPI DPC++/C++ Compiler

    DPCPP is built upon ICX as the underlying C++ Compiler, therefore most of this information
    also applies to DPCPP.

    Intel oneAPI Toolkit (DPC++/C++ Compiler)
        - Versioning: https://software.intel.com/content/www/us/en/develop/articles/oneapi-toolkit-version-to-compiler-version-mapping.html
        - Compiler: https://software.intel.com/content/www/us/en/develop/documentation/oneapi-dpcpp-cpp-compiler-dev-guide-and-reference/top.html
"""
import os
import platform
import textwrap

from conan.tools.env.environment import create_env_script
from conans.client.tools.win import is_win64, _system_registry_key
from conans.errors import ConanException


def is_using_intel_oneapi(compiler_version):
    """Check if the Intel compiler to be used belongs to Intel oneAPI

    Note: Intel oneAPI Toolkit first version is 2021.1
    """
    return int(compiler_version.split(".")[0]) >= 2021


def get_inteloneapi_installation_path():
    system = platform.system()
    # Let's try the default dirs
    if system == "Windows":
        if is_win64():
            base = r"SOFTWARE\WOW6432Node"
        else:
            base = r"SOFTWARE"
        path = r"{base}\Intel\Products\IntelOneAPI".format(base=base)
        from six.moves import winreg  # @UnresolvedImport
        installation_path = _system_registry_key(winreg.HKEY_LOCAL_MACHINE, path,
                                                 "ProductDIr")
        if not installation_path:
            raise ConanException("unable to find Intel oneAPI folder "
                                 "installation from Windows registry: %s" % path)
    elif system in ("Linux", "Darwin"):
        # If it was installed as root
        installation_path = os.path.join(os.sep, "opt", "intel", "oneapi")
        if not os.path.exists(installation_path):
            # Try if it was installed as a normal user
            installation_path = os.path.join(os.path.expanduser("~"), "intel", "oneapi")
        if not os.path.exists(installation_path):
            raise ConanException("Don't know how to find Intel oneAPI folder on %s" % system)
    else:
        raise ConanException("Your system is not supported by Intel oneAPI compilers.")

    return installation_path


class IntelOneAPI:
    """Intel oneAPI DPC++/C++/Classic Compilers"""

    filename = "conanintelsetvars"

    def __init__(self, conanfile):
        # Let's check the compatibility
        compiler_version = conanfile.settings.get_safe("compiler.version")
        mode = conanfile.settings.get_safe("compiler.mode")
        if is_using_intel_oneapi(compiler_version):
            if mode != "classic" and conanfile.settings.get_safe("os") == "Darwin":
                raise ConanException(
                    'macOS* is not supported for the icx/icpx or dpcpp compilers. '
                    'Use the "classic" mode (icc compiler) instead.')
        else:
            # Do not support legacy versions
            raise ConanException("You have to use 'intel' compiler which is meant for legacy "
                                 "versions like Intel Parallel Studio XE.")
        # Private properties
        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._compiler_version = compiler_version
        self._mode = mode
        self._out = conanfile.output
        # Public properties
        self.arch = conanfile.settings.get_safe("arch")

    @property
    def ms_toolset(self):
        if self._mode == "classic":
            # TODO: Get automatically the classic compiler version
            return "Intel C++ Compiler 19.2"
        elif self._mode == "icx":
            return "Intel C++ Compiler %s" % (self._compiler_version.split('.')[0])
        else:  # DPC++ compiler
            return "Intel(R) oneAPI DPC++ Compiler"

    def generate(self, group="build"):
        if platform.system() == "Windows" and not self._conanfile.win_bash:
            content = textwrap.dedent("""\
                @echo off
                {}
                """.format(self.command))
            filename = self.filename + '.bat'
        else:
            filename = self.filename + '.sh'
            content = self.command
        create_env_script(self._conanfile, content, filename, group)

    @property
    def installation_path(self):
        installation_path = self._conanfile.conf["tools.intel:installation_path"] or \
                            get_inteloneapi_installation_path()
        self._out.info("Got Intel oneAPI installation folder: %s" % installation_path)
        return installation_path

    @property
    def command(self):
        """
        The Intel oneAPI DPC++/C++ Compiler includes environment configuration scripts to
        configure your build and development environment variables:
            On Linux*, the file is a shell script called setvars.sh.
            On Windows*, the file is a batch file called setvars.bat.

        * Linux:
            >> . /<install-dir>/setvars.sh <arg1> <arg2> … <argn><arg1> <arg2> … <argn>

            The compiler environment script file accepts an optional target architecture
            argument <arg>:
                intel64: Generate code and use libraries for Intel 64 architecture-based targets.
                ia32: Generate code and use libraries for IA-32 architecture-based targets.
        * Windows:
            >> call <install-dir>\\setvars.bat [<arg1>] [<arg2>]

            Where <arg1> is optional and can be one of the following:
                intel64: Generate code and use libraries for Intel 64 architecture
                         (host and target).
                ia32: Generate code and use libraries for IA-32 architecture (host and target).
            With the dpcpp compiler, <arg1> is intel64 by default.

            The <arg2> is optional. If specified, it is one of the following:
                vs2019: Microsoft Visual Studio* 2019
                vs2017: Microsoft Visual Studio 2017

        :return: `str` setvars.sh|bat command to be run
        """
        # Let's check if user wants to use some custom arguments to run the setvars script
        command_args = self._conanfile.conf["tools.intel:setvars_args"] or ""
        # The setvars script is going to be loaded/cleared up every conanfile.run() execution
        # but we will check this env variable just in case
        if str(os.getenv("SETVARS_COMPLETED", "")) == "1" and "force" not in command_args:
            return "echo Conan:intel_setvars already set! Pass --force if you want to reload it"

        system = platform.system()
        svars = "setvars.bat" if system == "Windows" else "setvars.sh"
        command = '"%s"' % os.path.join(self.installation_path, svars)
        if system == "Windows":
            command = "call " + command
        else:
            command = ". " + command  # dot is more portable than source
        # If user has passed custom arguments
        if command_args:
            command += " %s" % command_args
            return command
        # Add architecture argument
        if self.arch == "x86_64":
            command += " intel64"
        elif self.arch == "x86":
            command += " ia32"
        else:
            raise ConanException("don't know how to call %s for %s" % (svars, self.arch))

        return command
