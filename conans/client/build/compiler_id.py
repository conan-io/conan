import os
import tempfile
from six import StringIO

from conans.client.runner import ConanRunner
from conans.model.version import Version


GCC = "gcc"
LLVM_GCC = "llvm-gcc"  # GCC frontend with LLVM backend
CLANG = "clang"
APPLE_CLANG = "apple-clang"
SUNCC = "suncc"
MSVC = "Visual Studio"
INTEL = "intel"
QCC = "qcc"


class CompilerId(object):
    """
    compiler identification description, holds compiler name, full version and
    other important properties
    """
    def __init__(self, name, major, minor, patch):
        self._name = name
        self._major = major
        self._minor = minor
        self._patch = patch
        self._version = Version(self.version)

    @property
    def name(self):
        return self._name

    @property
    def major(self):
        return self._major

    @property
    def minor(self):
        return self._minor

    @property
    def patch(self):
        return self._patch

    @property
    def version(self):
        return "%s.%s.%s" % (self._major, self._minor, self._patch)

    @property
    def major_minor(self):
        return "%s.%s" % (self._major, self._minor)

    def __str__(self):
        return "%s %s" % (self._name, self.version)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.name == other.name and self._version == other._version

    def __ne__(self, other):
        return not self.__eq__(other)


UNKNOWN_COMPILER = CompilerId(None, None, None, None)

# convert _MSC_VER to the corresponding Visual Studio version
MSVC_TO_VS_VERSION = {800: (1, 0),
                      900: (2, 0),
                      1000: (4, 0),
                      1010: (4, 1),
                      1020: (4, 2),
                      1100: (5, 0),
                      1200: (6, 0),
                      1300: (7, 0),
                      1310: (7, 1),
                      1400: (8, 0),
                      1500: (9, 0),
                      1600: (10, 0),
                      1700: (11, 0),
                      1800: (12, 0),
                      1900: (14, 0),
                      1910: (15, 0),
                      1911: (15, 3),
                      1912: (15, 5),
                      1913: (15, 6),
                      1914: (15, 7),
                      1915: (15, 8),
                      1916: (15, 9),
                      1920: (16, 0),
                      1921: (16, 1),
                      1922: (16, 2),
                      1923: (16, 3),
                      1924: (16, 4),
                      1925: (16, 5),
                      1926: (16, 6),
                      1927: (16, 7)}


def _parse_compiler_version(defines):
    try:
        if '__INTEL_COMPILER' in defines:
            compiler = INTEL
            version = int(defines['__INTEL_COMPILER'])
            major = int(version / 100)
            minor = int(version % 100)
            patch = int(defines['__INTEL_COMPILER_UPDATE'])
        elif '__clang__' in defines:
            compiler = APPLE_CLANG if '__apple_build_version__' in defines else CLANG
            major = int(defines['__clang_major__'])
            minor = int(defines['__clang_minor__'])
            patch = int(defines['__clang_patchlevel__'])
        elif '__SUNPRO_C' in defines or '__SUNPRO_CC' in defines:
            # In particular, the value of __SUNPRO_CC, which is a three-digit hex number.
            # The first digit is the major release. The second digit is the minor release.
            # The third digit is the micro release. For example, C++ 5.9 is 0x590.
            compiler = SUNCC
            define = '__SUNPRO_C' if '__SUNPRO_C' in defines else '__SUNPRO_CC'
            version = int(defines[define], 16)
            major = (version >> 8) & 0xF
            minor = (version >> 4) & 0xF
            patch = version & 0xF
        # MSVC goes after Clang and Intel, as they may define _MSC_VER
        elif '_MSC_VER' in defines:
            compiler = MSVC
            version = int(defines['_MSC_VER'])
            # map _MSC_VER into conan-friendly Visual Studio version
            # currently, conan uses major only, but here we store minor for the future as well
            # https://docs.microsoft.com/en-us/cpp/preprocessor/predefined-macros?view=vs-2019
            major, minor = MSVC_TO_VS_VERSION.get(version)
            patch = 0
        # GCC must be the last try, as other compilers may define __GNUC__ for compatibility
        elif '__GNUC__' in defines:
            if '__llvm__' in defines:
                compiler = LLVM_GCC
            elif '__QNX__' in defines:
                compiler = QCC
            else:
                compiler = GCC
            major = int(defines['__GNUC__'])
            minor = int(defines['__GNUC_MINOR__'])
            patch = int(defines['__GNUC_PATCHLEVEL__'])
        else:
            return UNKNOWN_COMPILER
        return CompilerId(compiler, major, minor, patch)
    except KeyError:
        return UNKNOWN_COMPILER
    except ValueError:
        return UNKNOWN_COMPILER
    except TypeError:
        return UNKNOWN_COMPILER


def detect_compiler_id(executable, runner=None):
    runner = runner or ConanRunner()
    # use a temporary file, as /dev/null might not be available on all platforms
    tmpname = tempfile.mktemp(suffix=".c")
    with open(tmpname, "wb") as f:
        f.write(b"\n")

    cmd = tempfile.mktemp(suffix=".cmd")
    with open(cmd, "wb") as f:
        f.write(b"echo off\nset MSC_CMD_FLAGS\n")

    detectors = [
        # "-dM" generate list of #define directives
        # "-E" run only preprocessor
        # "-x c" compiler as C code
        # the output is of lines in form of "#define name value"
        "-dM -E -x c",
        "--driver-mode=g++ -dM -E -x c",  # clang-cl
        "-c -xdumpmacros",  # SunCC,
        # cl (Visual Studio, MSVC)
        # "/nologo" Suppress Startup Banner
        # "/E" Preprocess to stdout
        # "/B1" C front-end
        # "/c" Compile Without Linking
        # "/TC" Specify Source File Type
        '/nologo /E /B1 "%s" /c /TC' % cmd,
        "/QdM /E /TC"  # icc (Intel) on Windows,
        "-Wp,-dM -E -x c"  # QNX QCC
    ]
    try:
        for detector in detectors:
            command = '%s %s "%s"' % (executable, detector, tmpname)
            result = StringIO()
            if 0 == runner(command, output=result):
                output = result.getvalue()
                defines = dict()
                for line in output.splitlines():
                    tokens = line.split(' ', 3)
                    if len(tokens) == 3 and tokens[0] == '#define':
                        defines[tokens[1]] = tokens[2]
                    # MSVC dumps macro definitions in single line:
                    # "MSC_CMD_FLAGS=-D_MSC_VER=1921 -Ze"
                    elif line.startswith("MSC_CMD_FLAGS="):
                        line = line[len("MSC_CMD_FLAGS="):].rstrip()
                        defines = dict()
                        tokens = line.split()
                        for token in tokens:
                            if token.startswith("-D") or token.startswith("/D"):
                                token = token[2:]
                                if '=' in token:
                                    name, value = token.split('=', 2)
                                else:
                                    name, value = token, '1'
                                defines[name] = value
                        break
                compiler = _parse_compiler_version(defines)
                if compiler == UNKNOWN_COMPILER:
                    continue
                return compiler
        return UNKNOWN_COMPILER
    finally:
        os.unlink(tmpname)
        os.unlink(cmd)
