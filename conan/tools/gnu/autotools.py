import json
import os

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conan.tools._compilers import use_win_mingw
from conans.util.files import load


class Autotools(object):

    def __init__(self, conanfile):
        """
        FIXME: include_rpath_flags CONAN 2.0 to default True? Could break many packages in center
        """
        self._conanfile = conanfile
        self._win_bash = False
        self._include_rpath_flags = False
        self._os = conanfile.settings.get_safe("os")
        self._os_version = conanfile.settings.get_safe("os.version")
        self._os_sdk = conanfile.settings.get_safe("os.sdk")
        self._os_subsystem = conanfile.settings.get_safe("os.subsystem")
        self._arch = conanfile.settings.get_safe("arch")
        self._build_type = conanfile.settings.get_safe("build_type")
        self._compiler = conanfile.settings.get_safe("compiler")
        self._compiler_version = conanfile.settings.get_safe("compiler.version")
        self._build = None
        self._host = None
        self._target = None
        if os.path.isfile(CONAN_TOOLCHAIN_ARGS_FILE):
            args = json.loads(load(CONAN_TOOLCHAIN_ARGS_FILE))
            self._build = args["build"] if "build" in args else None
            self._host = args["host"] if "host" in args else None
            self._target = args["target"] if "target" in args else None

    def configure(self):
        """
        http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html
        """
        if not self._conanfile.should_configure:
            return
        configure_dir = "."

        # TODO: Management of PKG_CONFIG_PATH
        # TODO: Implement management of --prefix, bindir, sbindir, libexecdir, libdir, includedir

        cmd = "%s/configure" % configure_dir
        cmd += ' --host=%s' % self._host if self._host else ''
        cmd += ' --build=%s' % self._build if self._build else ''
        cmd += ' --target=%s' % self._target if self._target else ''
        self._conanfile.output.info("Calling:\n > %s" % cmd)
        self._conanfile.run(cmd)

    def make(self):
        """if not self._build_type:
            raise ConanException("build_type setting should be defined.")
        with environment_append(vars or self.vars):
            str_args = args_to_string(args)
            cpu_count_option = (("-j%s" % cpu_count(output=self._conanfile.output))
                                if ("-j" not in str_args and "nmake" not in make_program.lower())
                                else None)
            self._conanfile.run("%s" % join_arguments([make_program, target, str_args,
                                                       cpu_count_option]),
                                win_bash=self._win_bash, subsystem=self.subsystem)"""

        make_program = self._conanfile.conf["tools.gnu:make_program"]
        if make_program is None:
            make_program = "mingw32-make" if use_win_mingw(self._conanfile) else "make"
        # Need to activate the buildenv if existing
        command = make_program
        self._conanfile.run(command)
