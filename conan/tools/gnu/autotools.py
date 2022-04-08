import os

from conan.tools.build import build_jobs
from conan.tools.files.files import load_toolchain_args
from conans.client.subsystems import subsystem_path, deduce_subsystem
from conans.client.build import join_arguments
from conans.tools import args_to_string


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
        configure_args = []
        if self._conanfile.package_folder:
            def _get_cpp_info_value(name):
                # Why not taking cpp.build? because this variables are used by the "cmake install"
                # that correspond to the package folder (even if the root is the build directory)
                elements = getattr(self._conanfile.cpp.package, name)
                return elements[0] if elements else None

            # If someone want arguments but not the defaults can pass them in args manually
            configure_args.extend(["--prefix=%s" % self._conanfile.package_folder.replace("\\", "/"),
                                   "--bindir=${prefix}/%s" % _get_cpp_info_value("bindirs"),
                                   "--sbindir=${prefix}/%s" % _get_cpp_info_value("bindirs"),
                                   "--libdir=${prefix}/%s" % _get_cpp_info_value("libdirs"),
                                   "--includedir=${prefix}/%s" % _get_cpp_info_value("includedirs"),
                                   "--oldincludedir=${prefix}/%s" % _get_cpp_info_value("includedirs"),
                                   "--datarootdir=${prefix}/%s" % _get_cpp_info_value("resdirs")])

        self._configure_args = self._configure_args + args_to_string(configure_args)
        source = self._conanfile.source_folder
        if build_script_folder:
            source = os.path.join(self._conanfile.source_folder, build_script_folder)

        configure_cmd = "{}/configure".format(source)
        subsystem = deduce_subsystem(self._conanfile, scope="build")
        configure_cmd = subsystem_path(subsystem, configure_cmd)
        cmd = '"{}" {}'.format(configure_cmd, self._configure_args)
        self._conanfile.output.info("Calling:\n > %s" % cmd)
        self._conanfile.run(cmd)

    def make(self, target=None):
        make_program = self._conanfile.conf.get("tools.gnu:make_program",
                                                default="mingw32-make" if self._use_win_mingw() else "make")
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
