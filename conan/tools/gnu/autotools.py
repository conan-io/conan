import json
import os

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conan.tools._compilers import use_win_mingw
from conan.tools.gnu.make import make_jobs_cmd_line_arg
from conans.util.files import load


class Autotools(object):

    def __init__(self, conanfile):
        """
        FIXME: include_rpath_flags CONAN 2.0 to default True? Could break many packages in center
        """
        self._conanfile = conanfile
        self._build = None
        self._host = None
        self._target = None
        self.environment_files = ["conanbuildenv", "conanautotoolstoolchain", "conanautotoolsdeps"]

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

        # TODO: Implement management of --prefix, bindir, sbindir, libexecdir, libdir, includedir

        cmd = "%s/configure" % configure_dir
        cmd += ' --host=%s' % self._host if self._host else ''
        cmd += ' --build=%s' % self._build if self._build else ''
        cmd += ' --target=%s' % self._target if self._target else ''
        self._conanfile.output.info("Calling:\n > %s" % cmd)
        self._conanfile.run(cmd, env=self.environment_files)

    def make(self):
        make_program = self._conanfile.conf["tools.gnu:make_program"]
        if make_program is None:
            make_program = "mingw32-make" if use_win_mingw(self._conanfile) else "make"
        # Need to activate the buildenv if existing
        jobs = ""
        if "nmake" not in make_program.lower():
            jobs = make_jobs_cmd_line_arg(self._conanfile) or ""
        self._conanfile.run("{} {}".format(make_program, jobs), env=self.environment_files)
