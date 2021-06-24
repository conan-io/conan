import json
import os

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conan.tools._compilers import use_win_mingw
from conan.tools.gnu.make import make_jobs_cmd_line_arg
from conans.client.build import join_arguments
from conans.util.files import load


class Autotools(object):

    def __init__(self, conanfile, win_shell=False):
        self._conanfile = conanfile
        self._win_shell = win_shell
        self.environment_files = ["conanbuildenv", "conanautotoolstoolchain", "conanautotoolsdeps",
                                  "conanvcvars"]

        args_path = os.path.join(conanfile.generators_folder, CONAN_TOOLCHAIN_ARGS_FILE)
        if os.path.isfile(args_path):
            args = json.loads(load(args_path))
            self._configure_args = args.get("configure_args")
            self._make_args = args.get("make_args")

    def configure(self):
        """
        http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html
        """
        # FIXME: Conan 2.0 Are we keeping the "should_XXX" properties???
        if not self._conanfile.should_configure:
            return

        cmd = "{}/configure {}".format(self._conanfile.source_folder, self._configure_args)
        self._conanfile.output.info("Calling:\n > %s" % cmd)
        self._conanfile.run(cmd, env=self.environment_files, new_win_bash=self._win_shell)

    def make(self, target=None):
        make_program = self._conanfile.conf["tools.gnu:make_program"]
        if make_program is None:
            make_program = "mingw32-make" if use_win_mingw(self._conanfile) else "make"

        str_args = self._make_args
        jobs = ""
        if "-j" not in str_args and "nmake" not in make_program.lower():
            jobs = make_jobs_cmd_line_arg(self._conanfile) or ""
        command = join_arguments([make_program, target, str_args, jobs])
        self._conanfile.run(command, env=self.environment_files, win_shell=self._win_shell)

    def install(self):
        if not self._conanfile.should_install:
            return
        self.make(target="install")
