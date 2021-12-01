import os

from conan.tools.build import build_jobs
from conan.tools.files import load_toolchain_args
from conan.tools.microsoft.subsystems import subsystem_path, deduce_subsystem
from conans.client.build import join_arguments


class Autotools(object):

    def __init__(self, conanfile, namespace=None):
        self._conanfile = conanfile

        toolchain_file_content = load_toolchain_args(self._conanfile.generators_folder,
                                                     namespace=namespace)
        self._configure_args = toolchain_file_content.get("configure_args")
        self._make_args = toolchain_file_content.get("make_args")

    def configure(self, build_script_folder=None):
        """
        http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html
        """
        source = self._conanfile.source_folder
        if build_script_folder:
            source = os.path.join(self._conanfile.source_folder, build_script_folder)

        configure_cmd = "{}/configure".format(source)
        subsystem = deduce_subsystem(self._conanfile, scope="build")
        configure_cmd = subsystem_path(subsystem, configure_cmd)
        cmd = "{} {}".format(configure_cmd, self._configure_args)
        self._conanfile.output.info("Calling:\n > %s" % cmd)
        self._conanfile.run(cmd)

    def make(self, target=None):
        make_program = self._conanfile.conf["tools.gnu:make_program"]
        if make_program is None:
            make_program = "mingw32-make" if self._use_win_mingw() else "make"

        str_args = self._make_args
        jobs = ""
        if "-j" not in str_args and "nmake" not in make_program.lower():
            njobs = build_jobs(self._conanfile)
            if njobs:
                jobs = "-j{}".format(njobs)
        command = join_arguments([make_program, target, str_args, jobs])
        self._conanfile.run(command)

    def install(self):
        self.make(target="install")

    def _use_win_mingw(self):
        if hasattr(self._conanfile, 'settings_build'):
            os_build = self._conanfile.settings_build.get_safe('os')
        else:
            os_build = self._conanfile.settings.get_safe("os")

        if os_build == "Windows":
            compiler = self._conanfile.settings.get_safe("compiler")
            sub = self._conanfile.settings.get_safe("os.subsystem")
            if sub in ("cygwin", "msys2", "msys") or compiler == "qcc":
                return False
            else:
                if self._conanfile.win_bash:
                    return False
                return True
        return False
