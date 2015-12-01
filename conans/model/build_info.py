import os
import re
from conans.errors import ConanException
from conans.client.generators import TXTGenerator


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


class CppInfo(_CppInfo):
    """ Build Information declared to be used by the CONSUMERS of a
    conans. That means that consumers must use this flags and configs i order
    to build properly.
    Defined in user CONANFILE, directories are relative at user definition time
    """
    def __init__(self, root_folder):
        super(CppInfo, self).__init__()
        self.root = root_folder  # the full path of the package in which the conans is found
        self.includedirs.append(DEFAULT_INCLUDE)
        self.libdirs.append(DEFAULT_LIB)
        self.bindirs.append(DEFAULT_BIN)
        self.resdirs.append(DEFAULT_RES)

    @property
    def include_paths(self):
        return [os.path.join(self.root, p) for p in self.includedirs]

    @property
    def lib_paths(self):
        return [os.path.join(self.root, p) for p in self.libdirs]

    @property
    def bin_paths(self):
        return [os.path.join(self.root, p) for p in self.bindirs]


class DepsCppInfo(_CppInfo):
    """ Build Information necessary to build a given conans. It contains the
    flags, directories and options if its dependencies. The conans CONANFILE
    should use these flags to pass them to the underlaying build system (Cmake, make),
    so deps info is managed
    """
    fields = ["includedirs", "libdirs", "bindirs", "libs", "defines", "cppflags",
              "cflags", "sharedlinkflags", "exelinkflags"]

    def __init__(self):
        super(DepsCppInfo, self).__init__()
        self._dependencies = {}

    @property
    def dependencies(self):
        return self._dependencies.iteritems()

    def __getitem__(self, item):
        return self._dependencies[item]

    def __repr__(self):
        return TXTGenerator(self).content

    @staticmethod
    def loads(text):
        pattern = re.compile("^\[([a-zA-Z0-9_-]{2,50})\]")
        result = DepsCppInfo()

        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] == '#':
                continue
            m = pattern.match(line)
            if m:
                group = m.group(1)
                tokens = group.split("_")
                field = tokens[0]
                if field not in DepsCppInfo.fields:
                    raise ConanException("Unrecognized field '%s'" % field)
                if len(tokens) == 2:
                    dep = tokens[1]
                    child = result._dependencies.setdefault(dep, DepsCppInfo())
                    current_field = getattr(child, field)
                else:
                    current_field = getattr(result, field)
            else:
                current_field.append(line)

        return result

    def update(self, dep_cpp_info, conan_ref=None):
        if conan_ref is not None:
            self._dependencies[conan_ref.name] = dep_cpp_info
        else:
            self._dependencies.update(dep_cpp_info.dependencies)

        for d in dep_cpp_info.include_paths:
            if d not in self.includedirs:
                self.includedirs.append(d)
        for d in dep_cpp_info.lib_paths:
            if d not in self.libdirs:
                self.libdirs.append(d)
        for d in dep_cpp_info.bin_paths:
            if d not in self.bindirs:
                self.bindirs.append(d)
        for d in dep_cpp_info.libs:
            if d not in self.libs:
                self.libs.append(d)
        for d in dep_cpp_info.defines:
            if d not in self.defines:
                self.defines.append(d)
        for d in dep_cpp_info.cppflags:
            if d not in self.cppflags:
                self.cppflags.append(d)
        for d in dep_cpp_info.sharedlinkflags:
            if d not in self.sharedlinkflags:
                self.sharedlinkflags.append(d)
        for d in dep_cpp_info.exelinkflags:
            if d not in self.exelinkflags:
                self.exelinkflags.append(d)
        for d in dep_cpp_info.cflags:
            if d not in self.cflags:
                self.cflags.append(d)

    @property
    def include_paths(self):
        return self.includedirs

    @property
    def lib_paths(self):
        return self.libdirs

    @property
    def bin_paths(self):
        return self.bindirs
