import copy
import os
import platform

from conans.client import join_arguments
from conans.client.build.compiler_flags import (architecture_flag, format_libraries,
                                                format_library_paths, format_defines,
                                                sysroot_flag, format_include_paths,
                                                build_type_flag, libcxx_flag, build_type_define,
                                                libcxx_define, pic_flag, rpath_flags)
from conans.client.build.cppstd_flags import cppstd_flag
from conans.client.tools.oss import OSInfo
from conans.client.tools.win import unix_path
from conans.tools import (environment_append, args_to_string, cpu_count, cross_building,
                          detected_architecture)


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
        self._arch = conanfile.settings.get_safe("arch")
        self._build_type = conanfile.settings.get_safe("build_type")
        self._compiler = conanfile.settings.get_safe("compiler")
        self._compiler_version = conanfile.settings.get_safe("compiler.version")
        self._libcxx = conanfile.settings.get_safe("compiler.libcxx")
        self._cppstd = conanfile.settings.get_safe("cppstd")

        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self.libs = copy.copy(self._deps_cpp_info.libs)
        self.include_paths = copy.copy(self._deps_cpp_info.include_paths)
        self.library_paths = copy.copy(self._deps_cpp_info.lib_paths)

        self.defines = self._configure_defines()
        # Will go to CFLAGS and CXXFLAGS ["-m64" "-m32", "-g", "-s"]
        self.flags = self._configure_flags()
        # Only c++ flags [-stdlib, -library], will go to CXXFLAGS
        self.cxx_flags = self._configure_cxx_flags()
        # cpp standard
        self.cppstd_flag = cppstd_flag(self._compiler, self._compiler_version, self._cppstd)
        # Not -L flags, ["-m64" "-m32"]
        self.link_flags = self._configure_link_flags()  # TEST!
        # Not declared by default
        self.fpic = None

    def _get_triplet(self, the_arch, the_os):
        """
        machine-vendor-op_system, But vendor can be omitted in practice
        """

        # Calculate the arch
        machine = {"x86": "i686" if the_os != "Linux" else "x86",
                   "x86_64": "x86_64",
                   "armv6": "arm",
                   "armv7": "arm",
                   "armv7s": "arm",
                   "armv7k": "arm",
                   "armv7hf": "arm",
                   "armv8": "aarch64"}.get(the_arch, None)
        if machine is None:
            self._conanfile.output.warn("Unknown '%s' machine, Conan doesn't know how to "
                                        "translate it to the GNU triplet, please report at "
                                        " https://github.com/conan-io/conan/issues" % the_arch)
            return "unknown"

        # Calculate the OS
        compiler = self._conanfile.settings.get_safe("compiler")
        if compiler == "gcc":
            windows_op = "w64-mingw32"
        elif compiler == "Visual Studio":
            windows_op = "windows-msvc"
        else:
            windows_op = "windows"

        op_system = {"Windows": windows_op,
                     "Linux": "linux-gnu",
                     "Darwin": "apple-darwin",
                     "Android": "linux-android",
                     "Macos": "apple-darwin",
                     "iOS": "apple-darwin",
                     "watchOS": "apple-darwin",
                     "tvOS": "apple-darwin"}.get(the_os, the_os.lower())

        if the_os in ("Linux", "Android"):
            if "arm" in the_arch and the_arch != "armv8":
                op_system += "eabi"

            if the_arch == "armv7hf" and the_os == "Linux":
                op_system += "hf"

        return "%s-%s" % (machine, op_system)

    def _get_host_build_target_flags(self, arch_detected, os_detected):
        """Based on google search for build/host triplets, it could need a lot
        and complex verification"""

        if not cross_building(self._conanfile.settings, os_detected, arch_detected):
            return False, False, False

        build = self._get_triplet(arch_detected, os_detected)
        host = self._get_triplet(self._conanfile.settings.get_safe("arch"),
                                 self._conanfile.settings.get_safe("os"))

        return build, host, None

    def configure(self, configure_dir=None, args=None, build=None, host=None, target=None,
                  pkg_config_paths=None):
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
        :return: None

        http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html

        """
        if configure_dir:
            configure_dir = configure_dir.rstrip("/")
        else:
            configure_dir = "."
        auto_build, auto_host, auto_target = None, None, None
        if build is None or host is None or target is None:
            arch_detected = detected_architecture() or platform.machine()
            os_detected = platform.system()
            flags = self._get_host_build_target_flags(arch_detected, os_detected)
            auto_build, auto_host, auto_target = flags
        triplet_args = []

        if build is not False:  # Skipped by user
            if build or auto_build:  # User specified value or automatic
                triplet_args.append("--build=%s" % (build or auto_build))

        if host is not False:   # Skipped by user
            if host or auto_host:  # User specified value or automatic
                triplet_args.append("--host=%s" % (host or auto_host))

        if target is not False:  # Skipped by user
            if target or auto_target:  # User specified value or automatic
                triplet_args.append("--target=%s" % (target or auto_target))

        if pkg_config_paths:
            pkg_env = {"PKG_CONFIG_PATH": os.pathsep.join(pkg_config_paths)}
        else:
            # If we are using pkg_config generator automate the pcs location, otherwise it could
            # read wrong files
            pkg_env = {"PKG_CONFIG_PATH": self._conanfile.build_folder} \
                if "pkg_config" in self._conanfile.generators else {}

        with environment_append(pkg_env):
            with environment_append(self.vars):
                configure_dir = self._adjust_path(configure_dir)
                command = '%s/configure %s %s' % (configure_dir,
                                                  args_to_string(args), " ".join(triplet_args))
                self._conanfile.output.info("Calling:\n > %s" % command)
                self._conanfile.run(command,
                                    win_bash=self._win_bash,
                                    subsystem=self.subsystem)

    def _adjust_path(self, path):
        if self._win_bash:
            path = unix_path(path, path_flavor=self.subsystem)
        return '"%s"' % path if " " in path else path

    def make(self, args="", make_program=None, target=None):
        make_program = os.getenv("CONAN_MAKE_PROGRAM") or make_program or "make"
        with environment_append(self.vars):
            str_args = args_to_string(args)
            cpu_count_option = ("-j%s" % cpu_count()) if "-j" not in str_args else None
            self._conanfile.run("%s" % join_arguments([make_program, target, str_args,
                                                       cpu_count_option]),
                                win_bash=self._win_bash, subsystem=self.subsystem)

    def _configure_link_flags(self):
        """Not the -L"""
        ret = copy.copy(self._deps_cpp_info.sharedlinkflags)
        ret.extend(self._deps_cpp_info.exelinkflags)
        arch_flag = architecture_flag(compiler=self._compiler, arch=self._arch)
        if arch_flag:
            ret.append(arch_flag)

        sysf = sysroot_flag(self._deps_cpp_info.sysroot, win_bash=self._win_bash,
                            subsystem=self.subsystem,
                            compiler=self._compiler)
        if sysf:
            ret.append(sysf)

        if self._include_rpath_flags:
            the_os = self._conanfile.settings.get_safe("os_build") or \
                 self._conanfile.settings.get_safe("os")
            ret.extend(rpath_flags(the_os, self._compiler, self._deps_cpp_info.lib_paths))

        return ret

    def _configure_flags(self):
        ret = copy.copy(self._deps_cpp_info.cflags)
        arch_flag = architecture_flag(compiler=self._compiler, arch=self._arch)
        if arch_flag:
            ret.append(arch_flag)
        btf = build_type_flag(compiler=self._compiler, build_type=self._build_type)
        if btf:
            ret.append(btf)
        srf = sysroot_flag(self._deps_cpp_info.sysroot, win_bash=self._win_bash,
                           subsystem=self.subsystem,
                           compiler=self._compiler)
        if srf:
            ret.append(srf)

        return ret

    def _configure_cxx_flags(self):
        ret = copy.copy(self._deps_cpp_info.cppflags)
        cxxf = libcxx_flag(compiler=self._compiler, libcxx=self._libcxx)
        if cxxf:
            ret.append(cxxf)
        return ret

    def _configure_defines(self):
        # requires declared defines
        ret = copy.copy(self._deps_cpp_info.defines)

        # Debug definition for GCC
        btf = build_type_define(build_type=self._build_type)
        if btf:
            ret.append(btf)

        # CXX11 ABI
        abif = libcxx_define(compiler=self._compiler, libcxx=self._libcxx)
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

        lib_paths = format_library_paths(self.library_paths, win_bash=self._win_bash,
                                         subsystem=self.subsystem, compiler=self._compiler)
        include_paths = format_include_paths(self.include_paths, win_bash=self._win_bash,
                                             subsystem=self.subsystem, compiler=self._compiler)

        ld_flags = append(self.link_flags, lib_paths)
        cpp_flags = append(include_paths, format_defines(self.defines, self._compiler))
        libs = format_libraries(self.libs, compiler=self._compiler)

        tmp_compilation_flags = copy.copy(self.flags)
        if self.fpic:
            tmp_compilation_flags.append(pic_flag(self._compiler))

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
               "LIBS": libs,
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
               "LIBS": libs.strip(),
               }

        return ret


def _environ_value_prefix(var_name, prefix=" "):
    if os.environ.get(var_name, ""):
        return "%s%s" % (prefix, os.environ.get(var_name, ""))
    else:
        return ""
