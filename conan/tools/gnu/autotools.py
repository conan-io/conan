import json
import os

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conan.tools._compilers import use_win_mingw
from conan.tools.gnu.make import make_jobs_cmd_line_arg
from conans.tools import args_to_string
from conans.util.files import load


class Autotools(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._build = None
        self._host = None
        self._target = None
        self.environment_files = ["conanbuildenv", "conanautotoolstoolchain", "conanautotoolsdeps"]

        if os.path.isfile(CONAN_TOOLCHAIN_ARGS_FILE):
            args = json.loads(load(CONAN_TOOLCHAIN_ARGS_FILE))
            self._build = args.get("build")
            self._host = args.get("host")
            self._target = args.get("target")

    def configure(self, args=None, default_install_args=False):
        """
        http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html
        """
        # FIXME: Conan 2.0 Are we keeping the "should_XXX" properties???
        if not self._conanfile.should_configure:
            return
        configure_dir = "."

        args = args or []
        if default_install_args:
            # If someone want arguments but not the defaults can pass them in args manually
            args.extend(self._install_args)

        args_str = args_to_string(args)
        cmd = "%s/configure" % configure_dir
        for flag, var in (("host", self._host), ("build", self._build), ("target", self._target)):
            cmd += ' --{}={}'.format(flag, var) if var and flag not in args_str else ''
        cmd += ' {}'.format(args_str)
        self._conanfile.output.info("Calling:\n > %s" % cmd)
        self._conanfile.run(cmd, env=self.environment_files)

    @property
    def _install_args(self):
        args = ["--prefix=%s" % self._conanfile.package_folder.replace("\\", "/"),
                "--bindir=${prefix}/bin",
                "--sbindir=${prefix}/bin",
                "--libdir=${prefix}/lib",
                "--includedir=${prefix}/include",
                "--oldincludedir=${prefix}/include",
                "--datarootdir=${prefix}/share"]
        return args

    def make(self, target=None):
        make_program = self._conanfile.conf["tools.gnu:make_program"]
        if make_program is None:
            make_program = "mingw32-make" if use_win_mingw(self._conanfile) else "make"
        # Need to activate the buildenv if existing
        jobs = ""
        if "nmake" not in make_program.lower():
            jobs = make_jobs_cmd_line_arg(self._conanfile) or ""
        arguments = [make_program, jobs, target]
        self._conanfile.run(" ".join(filter(None, arguments)), env=self.environment_files)

    def install(self):
        if not self._conanfile.should_install:
            return
        self.make(target="install")
