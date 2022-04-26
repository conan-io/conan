import os

from conan.tools.build import build_jobs
from conan.tools.files.files import load_toolchain_args
from conans.client.subsystems import subsystem_path, deduce_subsystem
from conans.client.build import join_arguments
from conans.tools import args_to_string
from conan.tools.files import chdir


class Autotools(object):

    def __init__(self, conanfile, namespace=None, build_script_folder=None):
        self._conanfile = conanfile

        toolchain_file_content = load_toolchain_args(self._conanfile.generators_folder,
                                                     namespace=namespace)
        self._configure_args = toolchain_file_content.get("configure_args")
        self._make_args = toolchain_file_content.get("make_args")
        self.default_configure_install_args = True
        self.build_script_folder = os.path.join(self._conanfile.source_folder, build_script_folder) \
            if build_script_folder else self._conanfile.source_folder

    def configure(self):
        """
        http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html
        """
        configure_args = []
        if self.default_configure_install_args and self._conanfile.package_folder:
            def _get_argument(argument_name, cppinfo_name):
                elements = getattr(self._conanfile.cpp.package, cppinfo_name)
                return "--{}=${{prefix}}/{}".format(argument_name, elements[0]) if elements else ""

            # If someone want arguments but not the defaults can pass them in args manually
            configure_args.extend(["--prefix=%s" % self._conanfile.package_folder.replace("\\", "/"),
                                   _get_argument("bindir", "bindirs"),
                                   _get_argument("sbindir", "bindirs"),
                                   _get_argument("libdir", "libdirs"),
                                   _get_argument("includedir", "includedirs"),
                                   _get_argument("oldincludedir", "includedirs"),
                                   _get_argument("datarootdir", "resdirs")])

        self._configure_args = "{} {}".format(self._configure_args, args_to_string(configure_args)) \
                               if configure_args else self._configure_args

        configure_cmd = "{}/configure".format(self.build_script_folder)
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

    @staticmethod
    def _collect_shared_lib_files(folder):
        result = []
        files = os.listdir(folder)
        for f in files:
            full_path = os.path.join(folder, f)
            name, ext = os.path.splitext(f)
            if ext == ".dylib" and not os.path.islink(full_path):
                result.append(f)
        return result

    def _fix_macos_install_paths(self):
        """
        fix LC_ID_DYLIB in Macos
        """
        shared_libs = []
        package_folder = self._conanfile.package_folder
        libdirs = getattr(self._conanfile.cpp.package, "libdirs")
        for folder in libdirs:
            full_folder = os.path.join(package_folder, folder)
            shared_libs.extend(self._collect_shared_lib_files(full_folder))
            for shared_lib in shared_libs:
                command = "install_name_tool -id @rpath/{} {}".format(shared_lib, os.path.join(full_folder, shared_lib))
                self._conanfile.run(command)

    def install(self):
        # FIXME: we have to run configure twice because the local flow won't work otherwise
        #  because there's no package_folder until the package step
        self.configure()
        self.make(target="install")
        if self._conanfile.settings.get_safe("os") == "Macos":
            self._fix_macos_install_paths()

    def autoreconf(self, args=None):
        command = ["autoreconf"]
        args = args or ["--force", "--install"]
        command.extend(args)
        command = join_arguments(command)
        with chdir(self, self._conanfile.source_folder):
            self._conanfile.run(command)

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
