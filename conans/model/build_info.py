import os
from collections import OrderedDict

import deprecation

from conans.errors import ConanException

DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"
DEFAULT_SHARE = "share"


class _CppInfo(object):
    """ Object that stores all the necessary information to build in C/C++.
    It is intended to be system independent, translation to
    specific systems will be produced from this info
    """
    def __init__(self):
        self.name = None
        self.system_deps = []
        self.includedirs = []  # Ordered list of include paths
        self.srcdirs = []  # Ordered list of source paths
        self.libdirs = []  # Directories to find libraries
        self.resdirs = []  # Directories to find resources, data, etc
        self.bindirs = []  # Directories to find executables and shared libs
        self.builddirs = []
        self.rootpaths = []
        self._libs = []  # The libs to link against
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cxxflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags
        self.rootpath = ""
        self.sysroot = ""
        self._include_paths = None
        self._lib_paths = None
        self._bin_paths = None
        self._build_paths = None
        self._res_paths = None
        self._src_paths = None
        self.version = None  # Version of the conan package
        self.description = None  # Description of the conan package
        # When package is editable, filter_empty=False, so empty dirs are maintained
        self.filter_empty = True
        self._deps = OrderedDict()

    @property
    def libs(self):
        if self._deps:
            deps = [v for v in self._deps.values()]
            deps_sorted = sorted(deps, key=lambda component: len(component.deps))
            return [dep.lib for dep in deps_sorted if dep.lib is not None]
        else:
            return self._libs

    @libs.setter
    def libs(self, libs):
        if self._deps:
            raise ConanException("Setting first level libs is not supported when Components are "
                                 "already in use")
        self._libs = libs

    def __getitem__(self, key):
        if self._libs:
            raise ConanException("Usage of Components with '.libs' values is not allowed")
        if key not in self._deps.keys():
            self._deps[key] = Component(self, key)
        return self._deps[key]

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self.rootpath, p)
                     if not os.path.isabs(p) else p for p in paths]
        if self.filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    @property
    def include_paths(self):
        if self._include_paths is None:
            includedirs = self.includedirs
            for key, value in self._deps.items():
                for directory in value.includedirs:
                    if directory not in includedirs:
                        includedirs.append(directory)
            self._include_paths = self._filter_paths(includedirs)
        return self._include_paths

    @property
    def lib_paths(self):
        if self._lib_paths is None:
            self._lib_paths = self._filter_paths(self.libdirs)
        return self._lib_paths

    @property
    def src_paths(self):
        if self._src_paths is None:
            self._src_paths = self._filter_paths(self.srcdirs)
        return self._src_paths

    @property
    def bin_paths(self):
        if self._bin_paths is None:
            self._bin_paths = self._filter_paths(self.bindirs)
        return self._bin_paths

    @property
    def build_paths(self):
        if self._build_paths is None:
            self._build_paths = self._filter_paths(self.builddirs)
        return self._build_paths

    @property
    def res_paths(self):
        if self._res_paths is None:
            self._res_paths = self._filter_paths(self.resdirs)
        return self._res_paths

    # Compatibility for 'cppflags' (old style property to allow decoration)
    @deprecation.deprecated(deprecated_in="1.13", removed_in="2.0", details="Use 'cxxflags' instead")
    def get_cppflags(self):
        return self.cxxflags

    @deprecation.deprecated(deprecated_in="1.13", removed_in="2.0", details="Use 'cxxflags' instead")
    def set_cppflags(self, value):
        self.cxxflags = value

    cppflags = property(get_cppflags, set_cppflags)


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
        self._deps = OrderedDict()

    @property
    def libs(self):
        if self._deps:
            deps = [v for v in self._deps.values()]
            deps_sorted = sorted(deps, key=lambda component: len(component.deps))
            return [dep.lib for dep in deps_sorted if dep.lib is not None]
        else:
            return self._libs

    @libs.setter
    def libs(self, libs):
        if self._deps:
            raise ConanException("Setting first level libs is not supported when Components are "
                                 "already in use")
        self._libs = libs

    def __getitem__(self, key):
        if self._libs:
            raise ConanException("Usage of Components with '.libs' values is not allowed")
        if key not in self._deps.keys():
            self._deps[key] = Component(self, key)
        return self._deps[key]

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


class Component(object):

    def __init__(self, parent, name):
        self._parent = parent
        self.name = name
        self.deps = []
        self._lib = None
        self._exe = None
        self.system_deps = []
        self._includedirs = []
        self._libdirs = []
        self._resdirs = []
        self._bindirs = []
        self._builddirs = []
        self.defines = []
        self.cflags = []
        self.cppflags = []
        self.cxxflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []

    @property
    def lib(self):
        return self._lib

    @lib.setter
    def lib(self, name):
        if self._exe:
            raise ConanException("'.exe' is already set for this Component")
        self._lib = name

    @property
    def exe(self):
        return self._exe

    @exe.setter
    def exe(self, name):
        if self._lib:
            raise ConanException("'.lib' is already set for this Component")
        self._exe = name

    @property
    def includedirs(self):
        return DirList(self._parent.includedirs, self._includedirs)

    @includedirs.setter
    def includedirs(self, value):
        self._includedirs = value

    @property
    def libdirs(self):
        return DirList(self._parent.libdirs, self._libdirs)

    @libdirs.setter
    def libdirs(self, value):
        self._libdirs = value

    @property
    def resdirs(self):
        return DirList(self._parent.resdirs, self._resdirs)

    @resdirs.setter
    def resdirs(self, value):
        self._resdirs = value

    @property
    def bindirs(self):
        return DirList(self._parent.bindirs, self._bindirs)

    @bindirs.setter
    def bindirs(self, value):
        self._bindirs = value

    @property
    def builddirs(self):
        return DirList(self._parent.builddirs, self._builddirs)

    @builddirs.setter
    def builddirs(self, value):
        self._builddirs = value


class DirList(object):

    def __init__(self, inherited_dirs=None, dirs=None):
        self._inherited_dirs = inherited_dirs or []
        self._dirs = dirs or []

    @property
    def _complete_list(self):
        return list(OrderedDict.fromkeys(self._inherited_dirs + self._dirs))

    def append(self, directory):
        self._dirs.append(directory)

    def extend(self, directories):
        self._dirs.extend(directories)

    def __getitem__(self, index):
        return self._complete_list[index]

    def __repr__(self):
        return str(self._complete_list)

    def __eq__(self, other):
        return self._complete_list == other

    def __len__(self):
        return len(self._complete_list)

    def insert(self, index, directory):
        self._dirs.insert(index, directory)


class _BaseDepsCppInfo(_CppInfo):

    def __init__(self):
        super(_BaseDepsCppInfo, self).__init__()

    def update(self, dep_cpp_info):

        def merge_lists(seq1, seq2):
            return [s for s in seq1 if s not in seq2] + seq2

        self.includedirs = merge_lists(self.includedirs, dep_cpp_info.include_paths)
        self.srcdirs = merge_lists(self.srcdirs, dep_cpp_info.src_paths)
        self.libdirs = merge_lists(self.libdirs, dep_cpp_info.lib_paths)
        self.bindirs = merge_lists(self.bindirs, dep_cpp_info.bin_paths)
        self.resdirs = merge_lists(self.resdirs, dep_cpp_info.res_paths)
        self.builddirs = merge_lists(self.builddirs, dep_cpp_info.build_paths)
        self.libs = merge_lists(self.libs, dep_cpp_info._libs)
        self.rootpaths.append(dep_cpp_info.rootpath)

        # Note these are in reverse order
        self.defines = merge_lists(dep_cpp_info.defines, self.defines)
        self.cxxflags = merge_lists(dep_cpp_info.cxxflags, self.cxxflags)
        self.cflags = merge_lists(dep_cpp_info.cflags, self.cflags)
        self.sharedlinkflags = merge_lists(dep_cpp_info.sharedlinkflags, self.sharedlinkflags)
        self.exelinkflags = merge_lists(dep_cpp_info.exelinkflags, self.exelinkflags)

        if not self.sysroot:
            self.sysroot = dep_cpp_info.sysroot

    @property
    def libs(self):
        return self._libs

    @libs.setter
    def libs(self, libs):
        self._libs = libs

    @property
    def include_paths(self):
        return self.includedirs

    @property
    def lib_paths(self):
        return self.libdirs

    @property
    def src_paths(self):
        return self.srcdirs

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
