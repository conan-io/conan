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
    """ Object that stores all the necessary information to build in C/C++.
    It is intended to be system independent, translation to
    specific systems will be produced from this info
    """
    def __init__(self):
        self.includedirs = []  # Ordered list of include paths
        self.libdirs = []  # Directories to find libraries
        self.resdirs = []  # Directories to find resources, data, etc
        self.bindirs = []  # Directories to find executables and shared libs
        self.builddirs = []
        self.libs = []  # The libs to link against
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cppflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags
        self.rootpath = ""
        self.sysroot = None

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

    @property
    def build_paths(self):
        return [os.path.join(self.rootpath, p)
                if not os.path.isabs(p) else p for p in self.builddirs]

    @property
    def res_paths(self):
        return [os.path.join(self.rootpath, p)
                if not os.path.isabs(p) else p for p in self.resdirs]


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
        self.builddirs.append("")
        # public_deps is needed to accumulate list of deps for cmake targets
        self.public_deps = []
        self.configs = {}

    def __getattr__(self, config):

        def _get_cpp_info():
            result = _CppInfo()
            result.rootpath = self.rootpath
            result.sysroot = self.sysroot
            result.includedirs.append(DEFAULT_INCLUDE)
            result.libdirs.append(DEFAULT_LIB)
            result.bindirs.append(DEFAULT_BIN)
            result.resdirs.append(DEFAULT_RES)
            result.builddirs.append("")
            return result

        return self.configs.setdefault(config, _get_cpp_info())


class _BaseDepsCppInfo(_CppInfo):
    def __init__(self):
        super(_BaseDepsCppInfo, self).__init__()

    def update(self, dep_cpp_info):

        def merge_lists(seq1, seq2):
            return [s for s in seq1 if s not in seq2] + seq2

        self.includedirs = merge_lists(self.includedirs, dep_cpp_info.include_paths)
        self.libdirs = merge_lists(self.libdirs, dep_cpp_info.lib_paths)
        self.bindirs = merge_lists(self.bindirs, dep_cpp_info.bin_paths)
        self.resdirs = merge_lists(self.resdirs, dep_cpp_info.res_paths)
        self.builddirs = merge_lists(self.builddirs, dep_cpp_info.build_paths)
        self.libs = merge_lists(self.libs, dep_cpp_info.libs)

        # Note these are in reverse order
        self.defines = merge_lists(dep_cpp_info.defines, self.defines)
        self.cppflags = merge_lists(dep_cpp_info.cppflags, self.cppflags)
        self.cflags = merge_lists(dep_cpp_info.cflags, self.cflags)
        self.sharedlinkflags = merge_lists(dep_cpp_info.sharedlinkflags, self.sharedlinkflags)
        self.exelinkflags = merge_lists(dep_cpp_info.exelinkflags, self.exelinkflags)

        if not self.sysroot:
            self.sysroot = dep_cpp_info.sysroot

    @property
    def include_paths(self):
        return self.includedirs

    @property
    def lib_paths(self):
        return self.libdirs

    @property
    def bin_paths(self):
        return self.bindirs

    @property
    def build_paths(self):
        return self.builddirs

    @property
    def res_paths(self):
        return self.resdirs


class DepsCppInfo(_BaseDepsCppInfo):
    """ Build Information necessary to build a given conans. It contains the
    flags, directories and options if its dependencies. The conans CONANFILE
    should use these flags to pass them to the underlaying build system (Cmake, make),
    so deps info is managed
    """

    def __init__(self):
        super(DepsCppInfo, self).__init__()
        self._dependencies = OrderedDict()
        self.configs = {}

    def __getattr__(self, config):
        return self.configs.setdefault(config, _BaseDepsCppInfo())

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
                tokens = var_name.split(":")
                if len(tokens) == 2:  # has config
                    var_name, config = tokens
                else:
                    config = None
                tokens = var_name.split("_", 1)
                field = tokens[0]
                if len(tokens) == 2:
                    dep = tokens[1]
                    dep_cpp_info = result._dependencies.setdefault(dep, CppInfo(root_folder=""))
                    if field == "rootpath":
                        lines = lines[0]
                    item_to_apply = dep_cpp_info
                else:
                    item_to_apply = result
                if config:
                    config_deps = getattr(item_to_apply, config)
                    setattr(config_deps, field, lines)
                else:
                    setattr(item_to_apply, field, lines)
        except Exception as e:
            logger.error(traceback.format_exc())
            raise ConanException("There was an error parsing  conaninfo.txt: %s" % str(e))

        return result

    def update(self, dep_cpp_info, pkg_name):
        assert isinstance(dep_cpp_info, CppInfo)
        self._dependencies[pkg_name] = dep_cpp_info
        super(DepsCppInfo, self).update(dep_cpp_info)
        for config, cpp_info in dep_cpp_info.configs.items():
            self.configs.setdefault(config, _BaseDepsCppInfo()).update(cpp_info)

    def update_deps_cpp_info(self, dep_cpp_info):
        assert isinstance(dep_cpp_info, DepsCppInfo)
        for pkg_name, cpp_info in dep_cpp_info.dependencies:
            self.update(cpp_info, pkg_name)
