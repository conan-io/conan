import copy
import os
import platform


from conans.client import tools
from conans.client.tools.oss import OSInfo,  cross_building, \
    detected_architecture, detected_os, get_gnu_triplet, get_target_os_arch, get_build_os_arch
from conans.client.tools.win import unix_path
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_BIN, DEFAULT_INCLUDE, DEFAULT_LIB, DEFAULT_SHARE
from conans.util.files import get_abs_path


class Autotools(object):

    def __init__(self, conanfile, win_bash=False, include_rpath_flags=False):
        """
        FIXME: include_rpath_flags CONAN 2.0 to default True? Could break many packages in center
        """
        self._conanfile = conanfile
        self._win_bash = win_bash
        self._include_rpath_flags = include_rpath_flags
        self.subsystem = OSInfo().detect_windows_subsystem() if self._win_bash else None
        self._os = conanfile.settings.get_safe("os")
        self._os_version = conanfile.settings.get_safe("os.version")
        self._os_sdk = conanfile.settings.get_safe("os.sdk")
        self._os_subsystem = conanfile.settings.get_safe("os.subsystem")
        self._arch = conanfile.settings.get_safe("arch")
        self._os_target, self._arch_target = get_target_os_arch(conanfile)
        self._build_type = conanfile.settings.get_safe("build_type")
        self._compiler = conanfile.settings.get_safe("compiler")
        self._compiler_version = conanfile.settings.get_safe("compiler.version")

        # Precalculate build, host, target triplets
        self.build, self.host, self.target = self._get_host_build_target_flags()

    def _get_host_build_target_flags(self):
        """Based on google search for build/host triplets, it could need a lot
        and complex verification"""

        if self._os_target and self._arch_target:
            try:
                target = get_gnu_triplet(self._os_target, self._arch_target, self._compiler)
            except ConanException as exc:
                self._conanfile.output.warn(str(exc))
                target = None
        else:
            target = None

        if hasattr(self._conanfile, 'settings_build'):
            os_build, arch_build = get_build_os_arch(self._conanfile)
        else:
            # FIXME: Why not use 'os_build' and 'arch_build' from conanfile.settings?
            os_build = detected_os() or platform.system()
            arch_build = detected_architecture() or platform.machine()

        if os_build is None or arch_build is None or self._arch is None or self._os is None:
            return False, False, target

        if not cross_building(self._conanfile, os_build, arch_build):
            return False, False, target

        try:
            build = get_gnu_triplet(os_build, arch_build, self._compiler)
        except ConanException as exc:
            self._conanfile.output.warn(str(exc))
            build = None
        try:
            host = get_gnu_triplet(self._os, self._arch, self._compiler)
        except ConanException as exc:
            self._conanfile.output.warn(str(exc))
            host = None
        return build, host, target

    def configure(self, configure_dir=None, args=None, build=None, host=None, target=None,
                  pkg_config_paths=None, vars=None, use_default_install_dirs=True):
        """
        http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html
        :param use_default_install_dirs: Use or not the defaulted installation dirs

        """
        if not self._conanfile.should_configure:
            return
        if configure_dir:
            configure_dir = configure_dir.rstrip("/")
        else:
            configure_dir = "."
        """
        triplet_args = []

        if build is not False:  # Skipped by user
            if build or self.build:  # User specified value or automatic
                triplet_args.append("--build=%s" % (build or self.build))

        if host is not False:   # Skipped by user
            if host or self.host:  # User specified value or automatic
                triplet_args.append("--host=%s" % (host or self.host))

        if target is not False:  # Skipped by user
            if target or self.target:  # User specified value or automatic
                triplet_args.append("--target=%s" % (target or self.target))

        if pkg_config_paths:
            pkg_env = {"PKG_CONFIG_PATH":
                       [os.pathsep.join(get_abs_path(f, self._conanfile.install_folder)
                                        for f in pkg_config_paths)]}
        else:
            # If we are using pkg_config generator automate the pcs location, otherwise it could
            # read wrong files
            pkg_env = {"PKG_CONFIG_PATH": [self._conanfile.install_folder]} \
                if "pkg_config" in self._conanfile.generators else None
        """
        configure_dir = self._adjust_path(configure_dir)

        """if self._conanfile.package_folder is not None:
            if not args:
                args = ["--prefix=%s" % self._conanfile.package_folder.replace("\\", "/")]
            elif not self._is_flag_in_args("prefix", args):
                args.append("--prefix=%s" % self._conanfile.package_folder.replace("\\", "/"))

            all_flags = ["bindir", "sbindir", "libexecdir", "libdir", "includedir", "oldincludedir",
                         "datarootdir"]
            help_output = self._configure_help_output(configure_dir)
            available_flags = [flag for flag in all_flags if "--%s" % flag in help_output]

            if use_default_install_dirs:
                for varname in ["bindir", "sbindir", "libexecdir"]:
                    if self._valid_configure_flag(varname, args, available_flags):
                        args.append("--%s=${prefix}/%s" % (varname, DEFAULT_BIN))
                if self._valid_configure_flag("libdir", args, available_flags):
                    args.append("--libdir=${prefix}/%s" % DEFAULT_LIB)
                for varname in ["includedir", "oldincludedir"]:
                    if self._valid_configure_flag(varname, args, available_flags):
                        args.append("--%s=${prefix}/%s" % (varname, DEFAULT_INCLUDE))
                if self._valid_configure_flag("datarootdir", args, available_flags):
                    args.append("--datarootdir=${prefix}/%s" % DEFAULT_SHARE)

        with environment_append(pkg_env):
            with environment_append(vars or self.vars):
                command = '%s/configure %s %s' % (configure_dir, args_to_string(args),
                                                  " ".join(triplet_args))
                self._conanfile.output.info("Calling:\n > %s" % command)
                self._conanfile.run(command, win_bash=self._win_bash, subsystem=self.subsystem)"""

        cmd = "bash -c 'source autotoolsdeps.sh && source autotools.sh && %s/configure'" % configure_dir
        self._conanfile.output.info("Calling:\n > %s" % cmd)
        self._conanfile.run(cmd, win_bash=self._win_bash, subsystem=self.subsystem)

    def _configure_help_output(self, configure_path):
        from six import StringIO  # Python 2 and 3 compatible
        mybuf = StringIO()
        try:
            self._conanfile.run("%s/configure --help" % configure_path, win_bash=self._win_bash,
                                output=mybuf)
        except ConanException as e:
            self._conanfile.output.warn("Error running `configure --help`: %s" % e)
            return ""
        return mybuf.getvalue()

    def _adjust_path(self, path):
        if self._win_bash:
            path = unix_path(path, path_flavor=self.subsystem)
        return '"%s"' % path if " " in path else path

    @staticmethod
    def _valid_configure_flag(varname, args, available_flags):
        return not AutoToolsBuildEnvironment._is_flag_in_args(varname, args) and \
               varname in available_flags

    @staticmethod
    def _is_flag_in_args(varname, args):
        flag = "--%s=" % varname
        return any([flag in arg for arg in args])

    def make(self, target=None):
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

        make_program = self._conanfile.conf["tools.gnu"].make_program
        if make_program is None:
            make_program = "mingw32-make" if platform.system() == "Windows" else "make"
        if platform.system() == "Windows":
            cmd = "autotoolsdeps.bat && autotools.bat && {}".format(make_program)
        else:
            cmd = "bash -c 'source autotoolsdeps.sh "\
                  "&& source autotools.sh && {}'".format(make_program)
        self._conanfile.run(cmd, win_bash=self._win_bash, subsystem=self.subsystem)

    def install(self, args=""):
        if not self._conanfile.should_install:
            return
        self.make(target="install")

    def _get_vars(self):
        def append(*args):
            ret = []
            for arg in args:
                if arg:
                    if isinstance(arg, list):
                        ret.extend(arg)
                    else:
                        ret.append(arg)
            return ret

        tmp_compilation_flags = copy.copy(self.flags)

        if tools.is_apple_os(self._os):
            concat = " ".join(tmp_compilation_flags)
            if os.environ.get("CFLAGS", None):
                concat += " " + os.environ.get("CFLAGS", None)
            if os.environ.get("CXXFLAGS", None):
                concat += " " + os.environ.get("CXXFLAGS", None)
            if self._os_version and "-version-min" not in concat and "-target" not in concat:
                tmp_compilation_flags.append(tools.apple_deployment_target_flag(self._os,
                                                                                self._os_version,
                                                                                self._os_sdk,
                                                                                self._os_subsystem,
                                                                                self._arch))
            if "-isysroot" not in concat and platform.system() == "Darwin":
                tmp_compilation_flags.extend(["-isysroot",
                                              tools.XCRun(self._conanfile.settings).sdk_path])
            if "-arch" not in concat and self._arch:
                tmp_compilation_flags.extend(["-arch", tools.to_apple_arch(self._arch)])

        cxx_flags = append(tmp_compilation_flags, self.cxx_flags, self.cppstd_flag)
        c_flags = tmp_compilation_flags

        return ld_flags, cpp_flags, libs, cxx_flags, c_flags
