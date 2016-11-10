import os
import re
from conans.errors import ConanException
from conans.util.log import logger
import traceback
from collections import OrderedDict


DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"


class _CppInfo(object):
    """ Object that stores all the necessary information to build in C/C++ a
    given conans. It is intended to be system independent, translation to
    specific systems will be produced from this info
    """
    def __init__(self):
        self.includedirs = []  # Ordered list of include paths
        self.libs = []  # The libs to link against
        self.libdirs = []  # Directories to find libraries
        self.resdirs = []  # Directories to find resources, data, etc
        self.bindirs = []  # Directories to find executables and shared libs
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cppflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags
        self.rootpath = ""


class CppInfo(_CppInfo):
    """ Build Information declared to be used by the CONSUMERS of a
    conans. That means that consumers must use this flags and configs i order
    to build properly.
    Defined in user CONANFILE, directories are relative at user definition time
    """
    def __init__(self, root_folder):
        super(CppInfo, self).__init__()
        self.rootpath = root_folder  # the full path of the package in which the conans is found
        self.includedirs.append(DEFAULT_INCLUDE)
        self.libdirs.append(DEFAULT_LIB)
        self.bindirs.append(DEFAULT_BIN)
        self.resdirs.append(DEFAULT_RES)
        self.deps = None

    @property
    def include_paths(self):
        return [os.path.join(self.rootpath, p)
                if not os.path.isabs(p) else p for p in self.includedirs]

    @property
    def lib_paths(self):
        return [os.path.join(self.rootpath, p)
                if not os.path.isabs(p) else p for p in self.libdirs]

    @property
    def bin_paths(self):
        return [os.path.join(self.rootpath, p)
                if not os.path.isabs(p) else p for p in self.bindirs]


class DepsCppInfo(_CppInfo):
    """ Build Information necessary to build a given conans. It contains the
    flags, directories and options if its dependencies. The conans CONANFILE
    should use these flags to pass them to the underlaying build system (Cmake, make),
    so deps info is managed
    """
    fields = ["includedirs", "libdirs", "bindirs", "libs", "defines", "cppflags",
              "cflags", "sharedlinkflags", "exelinkflags", "rootpath"]

    def __init__(self):
        super(DepsCppInfo, self).__init__()
        self._dependencies = OrderedDict()

    @property
    def dependencies(self):
        return self._dependencies.items()

    @property
    def deps(self):
        return self._dependencies.keys()

    def __getitem__(self, item):
        return self._dependencies[item]

    @staticmethod
    def loads(text):
        pattern = re.compile("^\[([a-zA-Z0-9_:-]+)\]([^\[]+)", re.MULTILINE)
        result = DepsCppInfo()

        try:
            for m in pattern.finditer(text):
                var_name = m.group(1)
                lines = []
                for line in m.group(2).splitlines():
                    line = line.strip()
                    if not line or line[0] == "#":
                        continue
                    lines.append(line)
                if not lines:
                    continue
                tokens = var_name.split("_")
                field = tokens[0]
                if len(tokens) == 2:
                    dep = tokens[1]
                    dep_cpp_info = result._dependencies.setdefault(dep, DepsCppInfo())
                    if field == "rootpath":
                        lines = lines[0]
                    setattr(dep_cpp_info, field, lines)
                else:
                    setattr(result, field, lines)
        except Exception as e:
            logger.error(traceback.format_exc())
            raise ConanException("There was an error parsing  conaninfo.txt: %s" % str(e))

        return result

    def update(self, dep_cpp_info, conan_ref):
        self._dependencies[conan_ref.name] = dep_cpp_info

        def merge_lists(seq1, seq2):
            return [s for s in seq1 if s not in seq2] + seq2

        self.includedirs = merge_lists(self.includedirs, dep_cpp_info.include_paths)
        self.libdirs = merge_lists(self.libdirs, dep_cpp_info.lib_paths)
        self.bindirs = merge_lists(self.bindirs, dep_cpp_info.bin_paths)
        self.libs = merge_lists(self.libs, dep_cpp_info.libs)

        # Note these are in reverse order
        self.defines = merge_lists(dep_cpp_info.defines, self.defines)
        self.cppflags = merge_lists(dep_cpp_info.cppflags, self.cppflags)
        self.cflags = merge_lists(dep_cpp_info.cflags, self.cflags)
        self.sharedlinkflags = merge_lists(dep_cpp_info.sharedlinkflags, self.sharedlinkflags)
        self.exelinkflags = merge_lists(dep_cpp_info.exelinkflags, self.exelinkflags)

    @property
    def include_paths(self):
        return self.includedirs

    @property
    def lib_paths(self):
        return self.libdirs

    @property
    def bin_paths(self):
        return self.bindirs
