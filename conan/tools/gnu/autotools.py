import os

from conan.tools.build import build_jobs, args_to_string
from conan.tools.files.files import load_toolchain_args
from conans.client.subsystems import subsystem_path, deduce_subsystem
from conan.tools.files import chdir
from conans.util.runners import check_output_runner


def join_arguments(args):
    return " ".join(filter(None, args))


class Autotools(object):

    def __init__(self, conanfile, namespace=None):
        """
        :param conanfile: The current recipe object. Always use ``self``.
        :param namespace: this argument avoids collisions when you have multiple toolchain calls in
                          the same recipe. By setting this argument, the *conanbuild.conf* file used
                          to pass information to the toolchain will be named as:
                          *<namespace>_conanbuild.conf*. The default value is ``None`` meaning that
                          the name of the generated file is *conanbuild.conf*. This namespace must
                          be also set with the same value in the constructor of the AutotoolsToolchain
                          so that it reads the information from the proper file.
        """
        self._conanfile = conanfile

        toolchain_file_content = load_toolchain_args(self._conanfile.generators_folder,
                                                     namespace=namespace)

        self._configure_args = toolchain_file_content.get("configure_args")
        self._make_args = toolchain_file_content.get("make_args")
        self._autoreconf_args = toolchain_file_content.get("autoreconf_args")

    def configure(self, build_script_folder=None, args=None):
        """
        Call the configure script.

        :param args: Extra arguments for configure
        :param build_script_folder: Subfolder where the `configure` script is located. If not specified
                                    conanfile.source_folder is used.
        """
        # http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        # https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html
        script_folder = os.path.join(self._conanfile.source_folder, build_script_folder) \
            if build_script_folder else self._conanfile.source_folder

        configure_args = []
        configure_args.extend(args or [])

        self._configure_args = "{} {}".format(self._configure_args, args_to_string(configure_args))

        configure_cmd = "{}/configure".format(script_folder)
        subsystem = deduce_subsystem(self._conanfile, scope="build")
        configure_cmd = subsystem_path(subsystem, configure_cmd)
        cmd = '"{}" {}'.format(configure_cmd, self._configure_args)
        self._conanfile.output.info("Calling:\n > %s" % cmd)
        self._conanfile.run(cmd)

    def make(self, target=None, args=None):
        """
        Call the make program.

        :param target: (Optional, Defaulted to ``None``): Choose which target to build. This allows
                       building of e.g., docs, shared libraries or install for some AutoTools
                       projects
        """
        make_program = self._conanfile.conf.get("tools.gnu:make_program",
                                                default="mingw32-make" if self._use_win_mingw() else "make")
        str_args = self._make_args
        str_extra_args = " ".join(args) if args is not None else ""
        jobs = ""
        if "-j" not in str_args and "nmake" not in make_program.lower():
            njobs = build_jobs(self._conanfile)
            if njobs:
                jobs = "-j{}".format(njobs)
        command = join_arguments([make_program, target, str_args, str_extra_args, jobs])
        self._conanfile.run(command)

    def _fix_osx_shared_install_name(self):

        def _osx_collect_dylibs(lib_folder):
            return [f for f in os.listdir(lib_folder) if f.endswith(".dylib")
                    and not os.path.islink(os.path.join(lib_folder, f))]

        def _fix_install_name(lib_name, lib_folder):
            command = "install_name_tool -id @rpath/{} {}".format(lib_name, os.path.join(lib_folder,
                                                                                         lib_name))
            self._conanfile.run(command)

        def _is_modified_install_name(lib_name, full_folder, libdir):
            """
            Check that the user did not change the default install_name using the install_name
            linker flag in that case we do not touch this field
            """
            command = "otool -D {}".format(os.path.join(full_folder, lib_name))
            install_path = check_output_runner(command).strip().split(":")[1].strip()
            default_path = str(os.path.join("/", libdir, shared_lib))
            return False if default_path == install_path else True

        libdirs = getattr(self._conanfile.cpp.package, "libdirs")
        for libdir in libdirs:
            full_folder = os.path.join(self._conanfile.package_folder, libdir)
            shared_libs = _osx_collect_dylibs(full_folder)
            for shared_lib in shared_libs:
                if not _is_modified_install_name(shared_lib, full_folder, libdir):
                    _fix_install_name(shared_lib, full_folder)

    def install(self, args=None):
        """
        This is just an "alias" of ``self.make(target="install")``

        """
        args = args if args is not None else ["DESTDIR={}".format(self._conanfile.package_folder)]
        self.make(target="install", args=args)
        if self._conanfile.settings.get_safe("os") == "Macos" and self._conanfile.options.get_safe("shared", False):
            self._fix_osx_shared_install_name()

    def autoreconf(self, args=None):
        args = args or []
        command = join_arguments(["autoreconf", self._autoreconf_args, args_to_string(args)])
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
