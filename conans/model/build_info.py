import os
from collections import OrderedDict

import deprecation

from conans.errors import ConanException

DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"
DEFAULT_SHARE = "share"
DEFAULT_BUILD = ""


class _CppInfo(object):
    """ Object that stores all the necessary information to build in C/C++.
    It is intended to be system independent, translation to
    specific systems will be produced from this info
    """
    def __init__(self):
        self.name = None
        self._system_deps = []
        self.includedirs = []  # Ordered list of include paths
        self.srcdirs = []  # Ordered list of source paths
        self.libdirs = []  # Directories to find libraries
        self.resdirs = []  # Directories to find resources, data, etc
        self.bindirs = []  # Directories to find executables and shared libs
        self.builddirs = []
        self.rootpaths = []
        self._libs = []  # The libs to link against
        self._exes = []
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
        self._components = OrderedDict()

    @property
    def _sorted_components(self):
        """
        Sorted components from less dependent to the most one
        :return: ordered list of components
        """
        # Sort first elements with less items in .deps attribute
        comps = sorted(self._components.values(), key=lambda component: len(component.deps))
        # Save name of unsorted elements
        unsorted_names = [comp.name for comp in comps]

        sorted_comps = []
        while unsorted_names:
            for comp in comps:
                # If element is already sorted, continue
                if comp.name not in unsorted_names:
                    continue
                # If element does not have deps or all of its deps are already sorted, sort this
                # element and remove it from the unsorted list
                elif not comp.deps or not [dep for dep in comp.deps if dep in unsorted_names]:
                    sorted_comps.append(comp)
                    unsorted_names.remove(comp.name)
        return sorted_comps

    @property
    def libs(self):
        if self._components:
            result = []
            for component in self._sorted_components:
                for sys_dep in component.system_deps:
                    if sys_dep and sys_dep not in result:
                        result.append(sys_dep)
                if component.lib:
                    result.append(component.lib)
            return result
        else:
            return self._libs

    @libs.setter
    def libs(self, libs):
        assert isinstance(libs, list), "'libs' attribute should be a list of strings"
        if self._components:
            raise ConanException("Setting first level libs is not supported when Components are "
                                 "already in use")
        self._libs = libs

    @property
    def exes(self):
        if self._components:
            return [component.exe for component in self._sorted_components if component.exe]
        else:
            return self._exes

    @exes.setter
    def exes(self, exes):
        assert isinstance(exes, list), "'exes' attribute should be a list of strings"
        if self._components:
            raise ConanException("Setting first level exes is not supported when Components are "
                                 "already in use")
        self._exes = exes

    @property
    def system_deps(self):
        if self._components:
            result = []
            for component in self._sorted_components:
                if component.system_deps:
                    for system_dep in component.system_deps:
                        if system_dep and system_dep not in result:
                            result.append(system_dep)
            return result
        else:
            return self._system_deps

    @system_deps.setter
    def system_deps(self, system_deps):
        assert isinstance(system_deps, list), "'system_deps' attribute should be a list of strings"
        if self._components:
            raise ConanException("Setting first level system_deps is not supported when Components "
                                 "are already in use")
        self._system_deps = system_deps

    def __getitem__(self, key):
        if self._libs:
            raise ConanException("Usage of Components with '.libs' values is not allowed")
        if key not in self._components.keys():
            self._components[key] = Component(self, key)
        return self._components[key]

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self.rootpath, p) for p in paths]
        if self.filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    def _get_paths(self, path_name):
        """
        Get the absolute paths either composing the lists from components or from the global
        variables. Also filter the values checking if the folders exist or not and avoid repeated
        values.
        :param path_name: name of the path variable to get (include_paths, res_paths...)
        :return: List of absolute paths
        """
        result = []

        if self._components:
            for dep_value in self._components.values():
                abs_paths = self._filter_paths(getattr(dep_value, "%s_paths" % path_name))
                for path in abs_paths:
                    if path not in result:
                        result.append(path)
        else:
            result = self._filter_paths(getattr(self, "%sdirs" % path_name))
        return result

    @property
    def include_paths(self):
        if self._include_paths is None:
            self._include_paths = self._get_paths("include")
        return self._include_paths

    @property
    def lib_paths(self):
        if self._lib_paths is None:
            self._lib_paths = self._get_paths("lib")
        return self._lib_paths

    @property
    def src_paths(self):
        if self._src_paths is None:
            self._src_paths = self._get_paths("src")
        return self._src_paths

    @property
    def bin_paths(self):
        if self._bin_paths is None:
            self._bin_paths = self._get_paths("bin")
        return self._bin_paths

    @property
    def build_paths(self):
        if self._build_paths is None:
            self._build_paths = self._get_paths("build")
        return self._build_paths

    @property
    def res_paths(self):
        if self._res_paths is None:
            self._res_paths = self._get_paths("res")
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
        self._default_dirs_values = {
            "includedirs": [DEFAULT_INCLUDE],
            "libdirs": [DEFAULT_LIB],
            "bindirs": [DEFAULT_BIN],
            "resdirs": [DEFAULT_RES],
            "builddirs": [DEFAULT_BUILD],
            "srcdirs": []
        }
        self.includedirs.extend(self._default_dirs_values["includedirs"])
        self.libdirs.extend(self._default_dirs_values["libdirs"])
        self.bindirs.extend(self._default_dirs_values["bindirs"])
        self.resdirs.extend(self._default_dirs_values["resdirs"])
        self.builddirs.extend(self._default_dirs_values["builddirs"])
        # public_deps is needed to accumulate list of deps for cmake targets
        self.public_deps = []
        self.configs = {}

    def _check_dirs_values(self):
        msg_template = "Using Components and global '{}' values ('{}') is not supported"
        for dir_name in self._default_dirs_values:
            dirs_value = getattr(self, dir_name)
            if dirs_value is not None and dirs_value != self._default_dirs_values[dir_name]:
                raise ConanException(msg_template.format(dir_name, dirs_value))

    def _clear_dirs_values(self):
        for dir_name in self._default_dirs_values:
            if getattr(self, dir_name) == self._default_dirs_values[dir_name]:
                self.__dict__[dir_name] = None

    def __getitem__(self, key):
        if self._libs or self._exes:
            raise ConanException("Usage of Components with '.libs' or '.exes' values is not allowed")
        self._clear_dirs_values()
        self._check_dirs_values()
        if key not in self._components:
            self._components[key] = Component(key, self.rootpath)
        return self._components[key]

    @property
    def components(self):
        return self._components

    def __getattr__(self, config):

        def _get_cpp_info():
            result = _CppInfo()
            result.rootpath = self.rootpath
            result.sysroot = self.sysroot
            result.includedirs.extend(self._default_dirs_values["includedirs"])
            result.libdirs.extend(self._default_dirs_values["libdirs"])
            result.bindirs.extend(self._default_dirs_values["bindirs"])
            result.resdirs.extend(self._default_dirs_values["resdirs"])
            result.builddirs.extend(self._default_dirs_values["builddirs"])
            return result

        return self.configs.setdefault(config, _get_cpp_info())


class Component(object):

    def __init__(self, name, root_folder):
        self._rootpath = root_folder
        self.name = name
        self.deps = []
        self._lib = None
        self._exe = None
        self.system_deps = []
        self.includedirs = [DEFAULT_INCLUDE]
        self.libdirs = [DEFAULT_LIB]
        self.resdirs = [DEFAULT_RES]
        self.bindirs = [DEFAULT_BIN]
        self.builddirs = [DEFAULT_BUILD]
        self.srcdirs = []
        self.defines = []
        self.cflags = []
        self.cppflags = []
        self.cxxflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []
        self._filter_empty = True

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self._rootpath, p) for p in paths]
        if self._filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    @property
    def lib(self):
        return self._lib

    @lib.setter
    def lib(self, name):
        assert isinstance(name, str), "'lib' attribute should be a string"
        if self._exe:
            raise ConanException("'.exe' is already set for this Component")
        self._lib = name

    @property
    def exe(self):
        return self._exe

    @exe.setter
    def exe(self, name):
        assert isinstance(name, str), "'exe' attribute should be a string"
        if self._lib:
            raise ConanException("'.lib' is already set for this Component")
        self._exe = name

    @property
    def include_paths(self):
        return self._filter_paths(self.includedirs)

    @property
    def lib_paths(self):
        return self._filter_paths(self.libdirs)

    @property
    def bin_paths(self):
        return self._filter_paths(self.bindirs)

    @property
    def build_paths(self):
        return self._filter_paths(self.builddirs)

    @property
    def res_paths(self):
        return self._filter_paths(self.resdirs)

    @property
    def src_paths(self):
        return self._filter_paths(self.srcdirs)


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
        self.libs = merge_lists(self.libs, dep_cpp_info.libs)
        self.exes = merge_lists(self.exes, dep_cpp_info.exes)
        self.rootpaths.append(dep_cpp_info.rootpath)

        # Note these are in reverse order
        self.defines = merge_lists(dep_cpp_info.defines, self.defines)
        self.cxxflags = merge_lists(dep_cpp_info.cxxflags, self.cxxflags)
        self.cflags = merge_lists(dep_cpp_info.cflags, self.cflags)
        self.sharedlinkflags = merge_lists(dep_cpp_info.sharedlinkflags, self.sharedlinkflags)
        self.exelinkflags = merge_lists(dep_cpp_info.exelinkflags, self.exelinkflags)
        self.system_deps = merge_lists(dep_cpp_info.system_deps, self.system_deps)

        if not self.sysroot:
            self.sysroot = dep_cpp_info.sysroot

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

