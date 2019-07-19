import os
from collections import OrderedDict
from copy import deepcopy

import deprecation

from conans.errors import ConanException
from conans.model.build_info_components import Component, DepComponent
from conans.model.build_info_components import DEFAULT_INCLUDE, DEFAULT_LIB, DEFAULT_BIN, \
    DEFAULT_RES, DEFAULT_SHARE, DEFAULT_BUILD


class CppInfo(object):
    """
    Build information about a dependency in the graph. Provide access to flags and relative
    paths. Information in this object can be modified and should be the input for the user
    """

    def __init__(self, root_folder):
        self.name = None
        self.system_deps = []
        self.includedirs = [DEFAULT_INCLUDE]  # Ordered list of include paths
        self.srcdirs = []  # Ordered list of source paths
        self.libdirs = [DEFAULT_LIB]  # Directories to find libraries
        self.resdirs = [DEFAULT_RES]  # Directories to find resources, data, etc
        self.bindirs = [DEFAULT_BIN]  # Directories to find executables and shared libs
        self.builddirs = [DEFAULT_BUILD]
        self.libs = []  # The libs to link against
        self.exes = []  # The exes
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cxxflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags
        self._rootpath = root_folder
        self.sysroot = ""
        self.version = None
        self.description = None
        # When package is editable, filter_empty=False, so empty dirs are maintained
        self.filter_empty = True  # FIXME: Should not be part of the public interface
        self._components = OrderedDict()
        self.public_deps = []
        self.configs = {}  # FIXME: Should not be part of the public interface

    @property
    def rootpath(self):
        return self._rootpath

    # Compatibility for 'cppflags'
    @deprecation.deprecated(deprecated_in="1.13", removed_in="2.0",
                            details="Use 'cxxflags' instead")
    def get_cppflags(self):
        return self.cxxflags

    # Compatibility for 'cppflags'
    @deprecation.deprecated(deprecated_in="1.13", removed_in="2.0",
                            details="Use 'cxxflags' instead")
    def set_cppflags(self, value):
        self.cxxflags = value

    # Old style property to allow deprecation decorators
    cppflags = property(get_cppflags, set_cppflags)

    def __getitem__(self, key):
        if key not in self._components:
            self._components[key] = Component(key, self.rootpath)
        return self._components[key]

    @property
    def components(self):
        return self._components.items()

    def __getattr__(self, config):
        if config not in self.configs:
            sub_cpp_info = CppInfo(self.rootpath)
            sub_cpp_info.filter_empty = self.filter_empty
            self.configs[config] = sub_cpp_info
        return self.configs[config]

    def as_dict(self):
        result = {}
        for name in ["name", "rootpath", "sysroot", "system_deps", "libs", "exes",
                     "includedirs", "srcdirs", "libdirs", "bindirs", "builddirs", "resdirs",
                     "defines", "cflags", "cxxflags", "cppflags", "sharedlinkflags", "exelinkflags"]:
            attr_name = "cxxflags" if name == "cppflags" else name  # Backwards compatibility
            result[name] = getattr(self, attr_name)
        result["components"] = {}
        for name, component in self.components:
            result["components"][name] = component.as_dict()
        result["configs"] = {}
        for config, cpp_info in self.configs.items():
            result["configs"][config] = cpp_info.as_dict()
        return result


class DepCppInfo(object):
    """
    Freezed build information about a dependency in the graph. Provide access to flags, relative
    paths and abslute paths. The information on this object should not be modified, so the interface
    to access values is done exposing them as properties.
    """

    def __init__(self, cpp_info):
        if cpp_info.components and (cpp_info.libs or cpp_info.exes):
            raise ConanException("Setting cpp_info.libs or cpp_info.exes and Components is not "
                                 "supported")
        self._cpp_info = cpp_info
        self._public_deps = cpp_info.public_deps
        # When package is editable, filter_empty=False, so empty dirs are maintained
        self.filter_empty = cpp_info.filter_empty
        self.configs = {}
        self._components = OrderedDict()
        # Copy Components
        for comp_name, comp_value in cpp_info.components:
            self._components[comp_name] = DepComponent(comp_value)
        # Copy Configurations
        for config, sub_cpp_info in cpp_info.configs.items():
            sub_dep_cpp_info = DepCppInfo(sub_cpp_info)
            sub_dep_cpp_info.filter_empty = self.filter_empty
            self.configs[config] = sub_dep_cpp_info
        # To initialize
        self._sorted_components = self._get_sorted_components()
        self._includedirs = self._get_relative_dirs("include")
        self._srcdirs = self._get_relative_dirs("src")
        self._libdirs = self._get_relative_dirs("lib")
        self._resdirs = self._get_relative_dirs("res")
        self._bindirs = self._get_relative_dirs("bin")
        self._builddirs = self._get_relative_dirs("build")
        self._include_paths = self._get_absolute_paths("include")
        self._src_paths = self._get_absolute_paths("src")
        self._lib_paths = self._get_absolute_paths("lib")
        self._res_paths = self._get_absolute_paths("res")
        self._bin_paths = self._get_absolute_paths("bin")
        self._build_paths = self._get_absolute_paths("build")
        self._defines = self._get_flags("defines")
        self._cflags = self._get_flags("cflags")
        self._cxxflags = self._get_flags("cxxflags")
        self._sharedlinkflags = self._get_flags("sharedlinkflags")
        self._exelinkflags = self._get_flags("exelinkflags")
        self._system_deps = self._get_system_deps()
        self._libs = self._get_libs()
        self._exes = self._get_exes()

    def __getattr__(self, config):
        if config not in self.configs:
            sub_dep_cpp_info = DepCppInfo(CppInfo(self.rootpath))
            sub_dep_cpp_info.filter_empty = self.filter_empty
            self.configs[config] = sub_dep_cpp_info
        return self.configs[config]

    def __getitem__(self, key):
        return self._components[key]

    def _get_sorted_components(self):
        """
        Sort Components from less dependent one first to the most dependent one last
        :return: List of sorted components
        """
        ordered = OrderedDict()
        components = deepcopy(self._components)
        while len(ordered) != len(self._components):
            # Search for next element to be processed
            for comp_name, comp in components.items():
                if comp_name in ordered:
                    continue
                # check if all the deps are declared
                if not all([dep in self._components for dep in comp.deps]):
                    raise ConanException("Component '%s' declares a missing dependency" % comp.name)
                # check if all the deps are already added to ordered
                if all([dep in ordered for dep in comp.deps]):
                    ordered[comp_name] = comp
                    del components[comp_name]
                    break
            else:
                raise ConanException("There is a dependency loop in the components declared in "
                                     "'self.cpp_info'")
        return list(ordered.values())

    def _get_relative_dirs(self, name):
        """
        Get the RELATIVE directories either composing the lists from components or from the global
        variables. Also filter the values checking if the folders exist or not and avoid repeated
        values.
        :param path_name: name of the type of path (include, bin, res...) to get the values from
        :return: List of relative paths
        """
        if self._components:
            result = []
            for dep_value in reversed(self._sorted_components):
                for _dir in getattr(dep_value, "%sdirs" % name):
                    if _dir not in result:
                        result.append(_dir)
        else:
            result = getattr(self._cpp_info, "%sdirs" % name)
        return result

    def _abs_filter_paths(self, paths):
        """
        Get absolute paths and filter the empty directories if needed
        """
        abs_paths = [os.path.join(self._cpp_info.rootpath, p) for p in paths]
        if self.filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    def _get_absolute_paths(self, path_name):
        """
        Get the ABSOLUTE paths either composing the lists from components or from the global
        variables. Also filter the values checking if the folders exist or not and avoid repeated
        values.
        :param path_name: name of the type of path (include, bin, res...) to get the values from
        :return: List of absolute paths
        """
        if self._components:
            result = []
            for dep_value in reversed(self._sorted_components):
                abs_paths = self._abs_filter_paths(getattr(dep_value, "%s_paths" % path_name))
                for path in abs_paths:
                    if path not in result:
                        result.append(path)
        else:
            result = self._abs_filter_paths(getattr(self._cpp_info, "%sdirs" % path_name))
        return result

    def _get_flags(self, name):
        """
        Get all the "flags" (defines, cxxflags, linker flags...) either composing the lists from
        components or from the global variables. Do NOT filter repeated values
        :param name: name of the "flag" (defines, cflags, sharedlinkflags...) to get the values from
        :return: list or ordered "flags"
        """
        if self._components:
            result = []
            for component in self._sorted_components:
                items = getattr(component, name)
                if items:
                    for item in items:
                        if item and item not in result:
                            result.extend(item)
            return result
        else:
            return getattr(self._cpp_info, "%s" % name)

    def _get_system_deps(self):
        if self._components:
            result = []
            for component in reversed(self._sorted_components):
                if component.system_deps:
                    for system_dep in component.system_deps:
                        if system_dep:
                            result.append(system_dep)
            return result
        else:
            return self._cpp_info.system_deps

    def _get_libs(self):
        if self._components:
            result = []
            for component in reversed(self._sorted_components):
                if component.lib and component.lib not in result:
                    result.append(component.lib)
                for sys_dep in component.system_deps:
                    if sys_dep and sys_dep:
                        result.append(sys_dep)
            return result
        else:
            return self._cpp_info.libs

    def _get_exes(self):
        if self._components:
            return [component.exe for component in self._sorted_components if component.exe]
        else:
            return self._cpp_info.exes

    @property
    def name(self):
        return self._cpp_info.name

    @property
    def version(self):
        return self._cpp_info.version

    @property
    def description(self):
        return self._cpp_info.description

    @property
    def public_deps(self):
        return self._cpp_info.public_deps

    @property
    def rootpath(self):
        return self._cpp_info.rootpath

    @property
    def sysroot(self):
        return self._cpp_info.sysroot

    @property
    def includedirs(self):
        return self._includedirs

    @property
    def srcdirs(self):
        return self._srcdirs

    @property
    def libdirs(self):
        return self._libdirs

    @property
    def resdirs(self):
        return self._resdirs

    @property
    def bindirs(self):
        return self._bindirs

    @property
    def builddirs(self):
        return self._builddirs

    @property
    def include_paths(self):
        return self._include_paths

    @property
    def src_paths(self):
        return self._src_paths

    @property
    def lib_paths(self):
        return self._lib_paths

    @property
    def res_paths(self):
        return self._res_paths

    @property
    def bin_paths(self):
        return self._bin_paths

    @property
    def build_paths(self):
        return self._build_paths

    @property
    def defines(self):
        return self._defines

    @property
    def cflags(self):
        return self._cflags

    @property
    def cxxflags(self):
        return self._cxxflags

    @property
    def sharedlinkflags(self):
        return self._sharedlinkflags

    @property
    def exelinkflags(self):
        return self._exelinkflags

    # Compatibility for 'cppflags'
    @property
    @deprecation.deprecated(deprecated_in="1.13", removed_in="2.0", details="Use 'cxxflags' instead")
    def cppflags(self):
        return self.cxxflags

    @property
    def system_deps(self):
        return self._system_deps

    @property
    def libs(self):
        return self._libs

    @property
    def exes(self):
        return self._exes

    @property
    def components(self):
        return self._components.items()

    def as_dict(self):
        result = {}
        fields = ["name", "rootpath", "sysroot", "description", "system_deps",
                  "libs", "exes", "version",
                  "includedirs", "srcdirs", "libdirs", "bindirs", "builddirs", "resdirs",
                  "include_paths", "src_paths", "lib_paths", "bin_paths", "build_paths", "res_paths",
                  "defines", "cflags", "cxxflags", "cppflags", "sharedlinkflags", "exelinkflags"]
        for field in fields:
            attr_name = "cxxflags" if field == "cppflags" else field  # Backwards compatibility
            result[field] = getattr(self, attr_name)
        result["components"] = {}
        for name, component in self.components:
            result["components"][name] = component.as_dict()
        result["configs"] = {}
        for config, dep_cpp_info in self.configs.items():
            result["configs"][config] = dep_cpp_info.as_dict()
        return result


class DepsCppInfo(object):
    """
    List of build information about each of the nodes in the graph.
    It contains the flags, directories and options if its dependencies.
    Provides properties to access aggregated information of directories and flags.
    The access to the information of each node can also be accessed.
    Should use these flags to pass them to the underlaying build system (Cmake, make),
    so deps info is managed.
    """

    def __init__(self):
        self._dependencies = OrderedDict()
        self.configs = {}

    def __getattr__(self, config):
        # If the configuration does not exist, return an empty list
        # FIXME: This could create unintended empty configurations for those generators/libs
        # that access unexisting configs with self.deps_cpp_info.whatever.includedirs
        return self.configs.setdefault(config, DepsCppInfo())

    @property
    def dependencies(self):
        return self._dependencies.items()

    @property
    def deps(self):
        return self._dependencies.keys()

    def __getitem__(self, item):
        return self._dependencies[item]

    def update(self, cpp_info, pkg_name):
        assert isinstance(cpp_info, CppInfo)
        self.update_dep_cpp_info(DepCppInfo(cpp_info), pkg_name)

    def update_dep_cpp_info(self, dep_cpp_info, pkg_name):
        assert isinstance(dep_cpp_info, DepCppInfo)
        self._dependencies[pkg_name] = dep_cpp_info
        if dep_cpp_info.configs:
            for config, sub_dep_cpp_info in dep_cpp_info.configs.items():
                self.configs.setdefault(config, DepsCppInfo()).update_dep_cpp_info(sub_dep_cpp_info,
                                                                                   pkg_name)

    @property
    def version(self):
        return None  # Backwards compatibility: Do not brake scons generator

    @property
    def description(self):
        return None  # Backwards compatibility

    @property
    def includedirs(self):
        return self._get_global_list("includedirs")

    @property
    def srcdirs(self):
        return self._get_global_list("srcdirs")

    @property
    def libdirs(self):
        return self._get_global_list("libdirs")

    @property
    def bindirs(self):
        return self._get_global_list("bindirs")

    @property
    def builddirs(self):
        return self._get_global_list("builddirs")

    @property
    def resdirs(self):
        return self._get_global_list("resdirs")

    @property
    def system_deps(self):
        return self._get_global_list("system_deps")

    @property
    def include_paths(self):
        return self._get_global_list("include_paths")

    @property
    def lib_paths(self):
        return self._get_global_list("lib_paths")

    @property
    def src_paths(self):
        return self._get_global_list("src_paths")

    @property
    def bin_paths(self):
        return self._get_global_list("bin_paths")

    @property
    def build_paths(self):
        return self._get_global_list("build_paths")

    @property
    def res_paths(self):
        return self._get_global_list("res_paths")

    @property
    def libs(self):
        return self._get_global_list("libs")

    @property
    def exes(self):
        return self._get_global_list("exes")

    @property
    def defines(self):
        return self._get_global_list("defines", reverse=True)

    @property
    def cflags(self):
        return self._get_global_list("cflags", reverse=True)

    @property
    def cxxflags(self):
        return self._get_global_list("cxxflags", reverse=True)

    @property
    def sharedlinkflags(self):
        return self._get_global_list("sharedlinkflags", reverse=True)

    @property
    def exelinkflags(self):
        return self._get_global_list("exelinkflags", reverse=True)

    @property
    def sysroot(self):
        sysroot_values = [sysroot for sysroot in self.sysroots if sysroot]
        if sysroot_values:
            return sysroot_values[0]
        return ""

    @property
    def rootpath(self):
        if self.rootpaths:
            return self.rootpaths[0]
        return ""

    @property
    def rootpaths(self):
        result = []
        for dep_cpp_info in self._dependencies.values():
            result.append(dep_cpp_info.rootpath)
        return result

    @property
    def sysroots(self):
        result = []
        for dep_cpp_info in self._dependencies.values():
            result.append(dep_cpp_info.sysroot)
        return result

    def _get_global_list(self, name, reverse=False):
        result = []
        deps_cpp_info = list(self._dependencies.values())
        if reverse:
            deps_cpp_info.reverse()
        for dep_cpp_info in deps_cpp_info:
            seq2 = getattr(dep_cpp_info, name, [])
            # FIXME: Complex logic to keep backwards compatibility of the order
            result = [s for s in result if s not in seq2] + seq2
        return result
