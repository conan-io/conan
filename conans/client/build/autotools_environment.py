import copy
import os
import platform

from conans.client.build import join_arguments
from conans.client.build.compiler_flags import (architecture_flag, build_type_define,
                                                build_type_flags, format_defines,
                                                format_include_paths, format_libraries,
                                                format_library_paths, libcxx_define, libcxx_flag,
                                                pic_flag, rpath_flags, sysroot_flag,
                                                format_frameworks, format_framework_paths)
from conans.client.build.cppstd_flags import cppstd_from_settings, \
    cppstd_flag_new as cppstd_flag
from conans.client import tools
from conans.client.tools.env import environment_append
from conans.client.tools.oss import OSInfo, args_to_string, cpu_count, cross_building, \
    detected_architecture, detected_os, get_gnu_triplet, get_target_os_arch, get_build_os_arch
from conans.client.tools.win import unix_path
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_BIN, DEFAULT_INCLUDE, DEFAULT_LIB, DEFAULT_SHARE
from conans.util.conan_v2_mode import conan_v2_error
from conans.util.files import get_abs_path


class AutoToolsBuildEnvironment(object):
    """
    - CPPFLAGS (C-PreProcesor-Flags NOT related with c++) (-I -D)
    - CFLAGS (not CPPFLAGS nor LDFLAGS, used for optimization or debugging)
    - CXXFLAGS (the CFLAGS for c++)
    - LDFLAGS (-L, others like -m64 -m32) linker
    """

    def __init__(self, conanfile, win_bash=False, include_rpath_flags=False):
        """
        FIXME: include_rpath_flags CONAN 2.0 to default True? Could break many packages in center
        """
        self._conanfile = conanfile
        self._win_bash = win_bash
        self._include_rpath_flags = include_rpath_flags
        self.subsystem = OSInfo().detect_windows_subsystem() if self._win_bash else None
        self._deps_cpp_info = conanfile.deps_cpp_info
        self._os = conanfile.settings.get_safe("os")
        self._os_version = conanfile.settings.get_safe("os.version")
        self._os_sdk = conanfile.settings.get_safe("os.sdk")
        self._os_subsystem = conanfile.settings.get_safe("os.subsystem")
        self._arch = conanfile.settings.get_safe("arch")
        self._os_target, self._arch_target = get_target_os_arch(conanfile)

        self._build_type = conanfile.settings.get_safe("build_type")

        self._compiler = conanfile.settings.get_safe("compiler")
        conan_v2_error("compiler setting should be defined.", not self._compiler)

        self._compiler_version = conanfile.settings.get_safe("compiler.version")
        self._compiler_runtime = conanfile.settings.get_safe("compiler.runtime")
        self._libcxx = conanfile.settings.get_safe("compiler.libcxx")
        self._cppstd = cppstd_from_settings(conanfile.settings)

        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self.libs = list(self._deps_cpp_info.libs)
        self.libs.extend(list(self._deps_cpp_info.system_libs))
        self.include_paths = list(self._deps_cpp_info.include_paths)
        self.library_paths = list(self._deps_cpp_info.lib_paths)

        self.defines = self._configure_defines()
        # Will go to CFLAGS and CXXFLAGS ["-m64" "-m32", "-g", "-s"]
        self.flags = self._configure_flags()
        # Only c++ flags [-stdlib, -library], will go to CXXFLAGS
        self.cxx_flags = self._configure_cxx_flags()
        # cpp standard
        self.cppstd_flag = cppstd_flag(conanfile.settings)
        # Not -L flags, ["-m64" "-m32"]
        self.link_flags = self._configure_link_flags()  # TEST!
        # Precalculate -fPIC
        self.fpic = self._configure_fpic()

        # Precalculate build, host, target triplets
        self.build, self.host, self.target = self._get_host_build_target_flags()

    def _configure_fpic(self):
        if not str(self._os).startswith("Windows"):
            fpic = self._conanfile.options.get_safe("fPIC")
            if fpic is not None:
                shared = self._conanfile.options.get_safe("shared")
                return True if (fpic or shared) else None

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
        :param pkg_config_paths: Optional paths to locate the *.pc files
        :param configure_dir: Absolute or relative path to the configure script
        :param args: Optional arguments to pass to configure.
        :param build: In which system the program will be built. "False" skips the --build flag
        :param host: In which system the generated program will run.  "False" skips the --host flag
        :param target: This option is only used to build a cross-compiling toolchain.
                       "False" skips the --target flag
                       When the tool chain generates executable program, in which target system
                       the program will run.

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

        configure_dir = self._adjust_path(configure_dir)

        if self._conanfile.package_folder is not None:
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
                self._conanfile.run(command, win_bash=self._win_bash, subsystem=self.subsystem)

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

    def make(self, args="", make_program=None, target=None, vars=None):
        if not self._conanfile.should_build:
            return
        conan_v2_error("build_type setting should be defined.", not self._build_type)
        make_program = os.getenv("CONAN_MAKE_PROGRAM") or make_program or "make"
        with environment_append(vars or self.vars):
            str_args = args_to_string(args)
            cpu_count_option = (("-j%s" % cpu_count(output=self._conanfile.output))
                                if ("-j" not in str_args and "nmake" not in make_program.lower())
                                else None)
            self._conanfile.run("%s" % join_arguments([make_program, target, str_args,
                                                       cpu_count_option]),
                                win_bash=self._win_bash, subsystem=self.subsystem)

    def install(self, args="", make_program=None, vars=None):
        if not self._conanfile.should_install:
            return
        self.make(args=args, make_program=make_program, target="install", vars=vars)

    def _configure_link_flags(self):
        """Not the -L"""
        ret = list(self._deps_cpp_info.sharedlinkflags)
        ret.extend(list(self._deps_cpp_info.exelinkflags))
        ret.extend(format_frameworks(self._deps_cpp_info.frameworks, self._conanfile.settings))
        ret.extend(format_framework_paths(self._deps_cpp_info.framework_paths,
                                          self._conanfile.settings))
        arch_flag = architecture_flag(self._conanfile.settings)
        if arch_flag:
            ret.append(arch_flag)

        sysf = sysroot_flag(self._deps_cpp_info.sysroot, self._conanfile.settings,
                            win_bash=self._win_bash,
                            subsystem=self.subsystem)
        if sysf:
            ret.append(sysf)

        if self._include_rpath_flags:
            os_build, _ = get_build_os_arch(self._conanfile)
            if not hasattr(self._conanfile, 'settings_build'):
                os_build = os_build or self._os
            ret.extend(rpath_flags(self._conanfile.settings, os_build,
                                   self._deps_cpp_info.lib_paths))

        return ret

    def _configure_flags(self):
        ret = list(self._deps_cpp_info.cflags)
        arch_flag = architecture_flag(self._conanfile.settings)
        if arch_flag:
            ret.append(arch_flag)
        btfs = build_type_flags(self._conanfile.settings)
        if btfs:
            ret.extend(btfs)
        srf = sysroot_flag(self._deps_cpp_info.sysroot,
                           self._conanfile.settings,
                           win_bash=self._win_bash,
                           subsystem=self.subsystem)
        if srf:
            ret.append(srf)
        if self._compiler_runtime:
            ret.append("-%s" % self._compiler_runtime)

        return ret

    def _configure_cxx_flags(self):
        ret = list(self._deps_cpp_info.cxxflags)
        cxxf = libcxx_flag(self._conanfile.settings)
        if cxxf:
            ret.append(cxxf)
        return ret

    def _configure_defines(self):
        # requires declared defines
        ret = list(self._deps_cpp_info.defines)

        # Debug definition for GCC
        btf = build_type_define(build_type=self._build_type)
        if btf:
            ret.append(btf)

        # CXX11 ABI
        abif = libcxx_define(self._conanfile.settings)
        if abif:
            ret.append(abif)
        return ret

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

        lib_paths = format_library_paths(self.library_paths,
                                         self._conanfile.settings,
                                         win_bash=self._win_bash,
                                         subsystem=self.subsystem)
        include_paths = format_include_paths(self.include_paths,
                                             self._conanfile.settings,
                                             win_bash=self._win_bash,
                                             subsystem=self.subsystem)

        ld_flags = append(self.link_flags, lib_paths)
        cpp_flags = append(include_paths, format_defines(self.defines))
        libs = format_libraries(self.libs, self._conanfile.settings)

        tmp_compilation_flags = copy.copy(self.flags)
        if self.fpic:
            tmp_compilation_flags.append(pic_flag(self._conanfile.settings))
        if tools.is_apple_os(self._os):
            concat = " ".join(tmp_compilation_flags)
            if os.environ.get("CFLAGS", None):
                concat += " " + os.environ.get("CFLAGS", None)
            if os.environ.get("CXXFLAGS", None):
                concat += " " + os.environ.get("CXXFLAGS", None)
            if (self._os_version and "-version-min" not in concat and "-target" not in concat) or \
                    self._os_subsystem:
                tmp_compilation_flags.append(tools.apple_deployment_target_flag(self._os,
                                                                                self._os_version,
                                                                                self._os_sdk,
                                                                                self._os_subsystem,
                                                                                self._arch))
            if "-isysroot" not in concat and platform.system() == "Darwin":
                isysroot = tools.XCRun(self._conanfile.settings).sdk_path
                if isysroot:
                    tmp_compilation_flags.extend(["-isysroot", isysroot])
            if "-arch" not in concat and self._arch:
                apple_arch = tools.to_apple_arch(self._arch)
                if apple_arch:
                    tmp_compilation_flags.extend(["-arch", apple_arch])

        cxx_flags = append(tmp_compilation_flags, self.cxx_flags, self.cppstd_flag)
        c_flags = tmp_compilation_flags

        return ld_flags, cpp_flags, libs, cxx_flags, c_flags

    @property
    def vars_dict(self):

        ld_flags, cpp_flags, libs, cxx_flags, c_flags = self._get_vars()

        if os.environ.get("CPPFLAGS", None):
            cpp_flags.append(os.environ.get("CPPFLAGS", None))

        if os.environ.get("CXXFLAGS", None):
            cxx_flags.append(os.environ.get("CXXFLAGS", None))

        if os.environ.get("CFLAGS", None):
            c_flags.append(os.environ.get("CFLAGS", None))

        if os.environ.get("LDFLAGS", None):
            ld_flags.append(os.environ.get("LDFLAGS", None))

        if os.environ.get("LIBS", None):
            libs.append(os.environ.get("LIBS", None))

        ret = {"CPPFLAGS": cpp_flags,
               "CXXFLAGS": cxx_flags,
               "CFLAGS": c_flags,
               "LDFLAGS": ld_flags,
               "LIBS": libs
               }

        return ret

    @property
    def vars(self):
        ld_flags, cpp_flags, libs, cxx_flags, c_flags = self._get_vars()

        cpp_flags = " ".join(cpp_flags) + _environ_value_prefix("CPPFLAGS")
        cxx_flags = " ".join(cxx_flags) + _environ_value_prefix("CXXFLAGS")
        cflags = " ".join(c_flags) + _environ_value_prefix("CFLAGS")
        ldflags = " ".join(ld_flags) + _environ_value_prefix("LDFLAGS")
        libs = " ".join(libs) + _environ_value_prefix("LIBS")

        ret = {"CPPFLAGS": cpp_flags.strip(),
               "CXXFLAGS": cxx_flags.strip(),
               "CFLAGS": cflags.strip(),
               "LDFLAGS": ldflags.strip(),
               "LIBS": libs.strip()
               }

        return ret


def _environ_value_prefix(var_name, prefix=" "):
    if os.environ.get(var_name, ""):
        return "%s%s" % (prefix, os.environ.get(var_name, ""))
    else:
        return ""
