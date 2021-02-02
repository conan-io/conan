import os
import platform
import re

from conan.tools.env import Environment
from conans.client.envvars.environment import env_files, BAT_FLAVOR, SH_FLAVOR
from conans.util.files import save


def format_include_paths(include_paths, settings, win_bash=False, subsystem=None):
    return ["-I%s" % adjust_path(include_path, settings, win_bash=win_bash, subsystem=subsystem)
            for include_path in include_paths if include_path]


def format_library_paths(library_paths, settings, win_bash=False, subsystem=None):
    compiler = settings.get_safe("compiler.base") or settings.get_safe("compiler")
    pattern = "-LIBPATH:%s" if str(compiler) == 'Visual Studio' else "-L%s"
    return [pattern % adjust_path(library_path, settings, win_bash=win_bash, subsystem=subsystem)
            for library_path in library_paths if library_path]


def unix_path(path, path_flavor=None):
    """"Used to translate windows paths to MSYS unix paths like
    c/users/path/to/file. Not working in a regular console or MinGW!"""
    return path
    if not path:
        return None

    if not OSInfo().is_windows:
        return path

    if os.path.exists(path):
        path = get_cased_path(path)  # if the path doesn't exist (and abs) we cannot guess the casing

    path_flavor = path_flavor or OSInfo.detect_windows_subsystem() or MSYS2
    path = path.replace(":/", ":\\")
    pattern = re.compile(r'([a-z]):\\', re.IGNORECASE)
    path = pattern.sub('/\\1/', path).replace('\\', '/')
    if path_flavor in (MSYS, MSYS2):
        return path.lower()
    elif path_flavor == CYGWIN:
        return '/cygdrive' + path.lower()
    elif path_flavor == WSL:
        return '/mnt' + path[0:2].lower() + path[2:]
    elif path_flavor == SFU:
        path = path.lower()
        return '/dev/fs' + path[0] + path[1:].capitalize()
    return None


GCC_LIKE = ['clang', 'apple-clang', 'gcc']


def format_frameworks(frameworks, settings):
    """
    returns an appropriate compiler flags to link with Apple Frameworks
    or an empty array, if Apple Frameworks aren't supported by the given compiler
    """
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    if (str(compiler) not in GCC_LIKE) and (str(compiler_base) not in GCC_LIKE):
        return []
    return ["-framework %s" % framework for framework in frameworks]


def format_framework_paths(framework_paths, settings):
    """
    returns an appropriate compiler flags to specify Apple Frameworks search paths
    or an empty array, if Apple Frameworks aren't supported by the given compiler
    """
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    if (str(compiler) not in GCC_LIKE) and (str(compiler_base) not in GCC_LIKE):
        return []
    return ["-F %s" % adjust_path(framework_path, settings) for framework_path in framework_paths]


def adjust_path(path, compiler, win_bash=False, subsystem=None):
    """
    adjusts path to be safely passed to the compiler command line
    for Windows bash, ensures path is in format according to the subsystem
    for path with spaces, places double quotes around it
    converts slashes to backslashes, or vice versa
    """
    if str(compiler) == 'Visual Studio':
        path = path.replace('/', '\\')
    else:
        path = path.replace('\\', '/')
    if win_bash:
        path = unix_path(path, subsystem)
    return '"%s"' % path if ' ' in path else path


def sysroot_flag(sysroot, settings, win_bash=False, subsystem=None):
    if not sysroot:
        return ""
    compiler = settings.get_safe("compiler.base") or settings.get_safe("compiler")
    if str(compiler) not in ('Visual Studio', 'msvc'):
        sysroot = adjust_path(sysroot, compiler, win_bash=win_bash, subsystem=subsystem)
        return '--sysroot={}'.format(sysroot)
    return ""


def format_libraries(libraries, settings):
    result = []
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    for library in libraries:
        if str(compiler) == 'Visual Studio' or str(compiler_base) == 'Visual Studio':
            if not library.endswith(".lib"):
                library += ".lib"
            result.append(library)
        else:
            result.append("-l%s" % library)
    return result


def format_defines(defines):
    return ["-D%s" % define for define in defines if define]


class AutotoolsDeps(object):
    def __init__(self, conanfile):
        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self._conanfile = conanfile
        self._deps_cpp_info = conanfile.deps_cpp_info
        self.libs = list(self._deps_cpp_info.libs)
        self.libs.extend(list(self._deps_cpp_info.system_libs))
        self.include_paths = list(self._deps_cpp_info.include_paths)
        self.library_paths = list(self._deps_cpp_info.lib_paths)
        self.defines = list(self._deps_cpp_info.defines)
        self.cflags = list(self._deps_cpp_info.cflags)
        self.cxx_flags = list(self._deps_cpp_info.cxxflags)
        self.sharedlinkflags = list(self._deps_cpp_info.sharedlinkflags)
        self.exelinkflags = list(self._deps_cpp_info.exelinkflags)
        self.frameworks = format_frameworks(self._deps_cpp_info.frameworks, self._conanfile.settings)
        self.frameworks_paths = format_framework_paths(self._deps_cpp_info.framework_paths,
                                                       self._conanfile.settings)

        # Simplified, not Windows bash or subsystem
        srf = sysroot_flag(self._deps_cpp_info.sysroot, self._conanfile.settings)
        if srf:
            self.cflags.append(srf)
            self.link_flags.append(srf)

    def generate(self):
        cpp_flags = []
        #include_paths = format_include_paths(self.include_paths, self._conanfile.settings)
        include_paths = ['-I"%s"' % p for p in self.include_paths]
        cpp_flags.extend(include_paths)
        cpp_flags.extend(format_defines(self.defines))

        # Libs
        libs = format_libraries(self.libs, self._conanfile.settings)

        # Ldflags
        ldflags = self.sharedlinkflags
        ldflags.extend(self.exelinkflags)
        ldflags.extend(self.frameworks)
        ldflags.extend(self.frameworks_paths)
        # lib_paths = format_library_paths(self.library_paths, self._conanfile.settings)
        lib_paths = ['-L"%s"' % p for p in self.library_paths]
        ldflags.extend(lib_paths)

        env = Environment()
        env["CPPFLAGS"].append(cpp_flags)
        env["LIBS"].append(libs)
        env["LDFLAGS"].append(ldflags)
        env.save_sh("autotoolsdeps.sh")
        env.save_bat("autotoolsdeps.bat")

    @property
    def _vars(self):
        cpp_flags = " ".join(cpp_flags)
        cxx_flags = " ".join(self.cxx_flags)
        cflags = " ".join(self.cflags)
        ldflags = " ".join(ldflags)
        libs = " ".join(libs)

        ret = {"CPPFLAGS": cpp_flags.strip(),
               "CXXFLAGS": cxx_flags.strip(),
               "CFLAGS": cflags.strip(),
               "LDFLAGS": ldflags.strip(),
               "LIBS": libs.strip()
               }
        return ret
