import os
from collections import OrderedDict

import deprecation

from conans.errors import ConanException
from conans.model.build_info_components import Component, DepComponent

DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"
DEFAULT_SHARE = "share"
DEFAULT_BUILD = ""


class CppInfo(object):

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
        self._sysroot = root_folder
        self.version = None
        self.description = None
        # When package is editable, filter_empty=False, so empty dirs are maintained
        self._filter_empty = True
        self._components = OrderedDict()
        self.public_deps = []
        self.configs = {}    # FIXME: Should not be part of the public interface
        self._default_values = {
            "includedirs": [DEFAULT_INCLUDE],
            "libdirs": [DEFAULT_LIB],
            "bindirs": [DEFAULT_BIN],
            "resdirs": [DEFAULT_RES],
            "builddirs": [DEFAULT_BUILD],
            "srcdirs": [],
            "libs": [],
            "exes": [],
            "defines": [],
            "cflags": [],
            "cxxflags": [],
            "sharedlinkflags": [],
            "exelinkflags": []
        }

    @property
    def rootpath(self):
        return self._rootpath

    @property
    def sysroot(self):
        return self._sysroot

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

    def _check_and_clear_default_values(self):
        for dir_name in self._default_values:
            dirs_value = getattr(self, dir_name)
            if dirs_value is not None and dirs_value != self._default_values[dir_name]:
                msg_template = "Using Components and global '{}' values ('{}') is not supported"
                raise ConanException(msg_template.format(dir_name, dirs_value))
            else:
                self.__dict__[dir_name] = None

    def __getitem__(self, key):
        self._check_and_clear_default_values()
        if key not in self._components:
            self._components[key] = Component(key, self.rootpath)
        return self._components[key]

    @property
    def components(self):
        return self._components

    def __getattr__(self, config):
        if config not in self.configs:
            sub_cpp_info = CppInfo(self.rootpath)
            sub_cpp_info._filter_empty = self._filter_empty
            self.configs[config] = sub_cpp_info
        return self.configs[config]

    def as_dict(self):
        result = {}
        for name in ["name", "rootpath", "sysroot", "description", "system_deps", "libs", "exes",
                     "includedirs", "srcdirs", "libdirs", "bindirs", "builddirs", "resdirs",
                     "defines", "cflags", "cxxflags", "cppflags", "sharedlinkflags", "exelinkflags"]:
            attr_name = "cxxflags" if name == "cppflags" else name  # Backwards compatibility
            result[name] = getattr(self, attr_name)
        result["components"] = {}
        for name, component in self.components.items():
            result["components"][name] = component.as_dict()
        result["configs"] = {}
        for config, cpp_info in self.configs.items():
            result["configs"][config] = cpp_info.as_dict()
        return result


class DepCppInfo(object):

    def __init__(self, cpp_info):
        self._name = cpp_info.name
        self._version = cpp_info.version
        self._description = cpp_info.description
        self._rootpath = cpp_info.rootpath
        self._system_deps = cpp_info.system_deps
        self._includedirs = cpp_info.includedirs
        self._srcdirs = cpp_info.srcdirs
        self._libdirs = cpp_info.libdirs
        self._resdirs = cpp_info.resdirs
        self._bindirs = cpp_info.bindirs
        self._builddirs = cpp_info.builddirs
        self._libs = cpp_info.libs
        self._exes = cpp_info.exes
        self._defines = cpp_info.defines
        self._cflags = cpp_info.cflags
        self._cxxflags = cpp_info.cxxflags
        self._sharedlinkflags = cpp_info.sharedlinkflags
        self._exelinkflags = cpp_info.exelinkflags
        self._include_paths = None
        self._lib_paths = None
        self._bin_paths = None
        self._build_paths = None
        self._res_paths = None
        self._src_paths = None
        self._public_deps = cpp_info.public_deps
        self.configs = {}
        # When package is editable, filter_empty=False, so empty dirs are maintained
        self._filter_empty = cpp_info._filter_empty
        self._components = OrderedDict()
        for comp_name, comp_value in cpp_info.components.items():
            self._components[comp_name] = DepComponent(comp_value)
        for config, sub_cpp_info in cpp_info.configs.items():
            sub_dep_cpp_info = DepCppInfo(sub_cpp_info)
            sub_dep_cpp_info._filter_empty = self._filter_empty
            self.configs[config] = sub_dep_cpp_info

    def __getattr__(self, config):
        if config not in self.configs:
            sub_dep_cpp_info = DepCppInfo(CppInfo(self.rootpath))
            sub_dep_cpp_info._filter_empty = self._filter_empty
            self.configs[config] = sub_dep_cpp_info
        return self.configs[config]

    def __getitem__(self, key):
        return self._components[key]

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self.rootpath, p) for p in paths]
        if self._filter_empty:
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
            for dep_value in self._sorted_components:
                abs_paths = self._filter_paths(getattr(dep_value, "%s_paths" % path_name))
                for path in abs_paths:
                    if path not in result:
                        result.append(path)
        else:
            result = self._filter_paths(getattr(self, "_%sdirs" % path_name))
        return result

    def _get_dirs(self, name):
        result = []
        if self._components:
            for dep_value in self._sorted_components:
                for _dir in getattr(dep_value, name):
                    if _dir not in result:
                        result.append(_dir)
        else:
            result = getattr(self, "_%s" % name)
        return result

    def _get_flags(self, name):
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
            return getattr(self, "_%s" % name)

    @property
    def _sorted_components(self):
        ordered = OrderedDict()
        while len(ordered) != len(self._components):
            # Search for next element to be processed
            for comp_name, comp in self._components.items():
                if comp_name in ordered:
                    continue
                # check if all the deps are declared
                if not all([dep in self._components for dep in comp.deps]):
                    raise ConanException("Component '%s' declares a missing dependency" % comp.name)
                # check if all the deps are already added to ordered
                if all([dep in ordered for dep in comp.deps]):
                    break
            else:
                raise ConanException("There is a dependency loop in the components declared in "
                                     "'self.cpp_info'")

            ordered[comp_name] = comp
        return ordered.values()

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def description(self):
        return self._description

    @property
    def public_deps(self):
        return self._public_deps

    @property
    def rootpath(self):
        return self._rootpath

    @property
    def sysroot(self):
        return self._rootpath

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

    @property
    def includedirs(self):
        return self._get_dirs("includedirs")

    @property
    def srcdirs(self):
        return self._get_dirs("srcdirs")

    @property
    def libdirs(self):
        return self._get_dirs("libdirs")

    @property
    def resdirs(self):
        return self._get_dirs("resdirs")

    @property
    def bindirs(self):
        return self._get_dirs("bindirs")

    @property
    def builddirs(self):
        return self._get_dirs("builddirs")

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

    @property
    def exes(self):
        if self._components:
            return [component.exe for component in self._sorted_components if component.exe]
        else:
            return self._exes

    @property
    def defines(self):
        return self._get_flags("defines")

    @property
    def cflags(self):
        return self._get_flags("cflags")

    @property
    def cxxflags(self):
        return self._get_flags("cxxflags")

    @property
    def sharedlinkflags(self):
        return self._get_flags("sharedlinkflags")

    @property
    def exelinkflags(self):
        return self._get_flags("exelinkflags")

    # Compatibility for 'cppflags'
    @property
    @deprecation.deprecated(deprecated_in="1.13", removed_in="2.0", details="Use 'cxxflags' instead")
    def cppflags(self):
        return self.cxxflags

    @property
    def components(self):
        return self._components

    def as_dict(self):
        result = {}
        for name in ["name", "rootpath", "sysroot", "description", "system_deps", "libs", "exes",
                     "includedirs", "srcdirs", "libdirs", "bindirs", "builddirs", "resdirs",
                     "include_paths", "src_paths", "lib_paths", "bin_paths", "build_paths", "res_paths",
                     "defines", "cflags", "cxxflags", "cppflags", "sharedlinkflags", "exelinkflags"]:
            attr_name = "cxxflags" if name == "cppflags" else name  # Backwards compatibility
            result[name] = getattr(self, attr_name)
        result["components"] = {}
        for name, component in self.components.items():
            result["components"][name] = component.as_dict()
        result["configs"] = {}
        for config, dep_cpp_info in self.configs.items():
            result["configs"][config] = dep_cpp_info.as_dict()
        return result


class DepsCppInfo(object):
    """ Build Information necessary to build a given conans. It contains the
    flags, directories and options if its dependencies. The conans CONANFILE
    should use these flags to pass them to the underlaying build system (Cmake, make),
    so deps info is managed
    """

    def __init__(self):
        self._dependencies = OrderedDict()
        self.configs = {}

    def __getattr__(self, config):
        if config not in self.configs:  #FIXME: Do we want to support this? try removing
            self.configs[config] = DepsCppInfo()
        return self.configs[config]

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
                if config not in self.configs:
                    self.configs[config] = DepsCppInfo()
                self.configs[config].update_dep_cpp_info(sub_dep_cpp_info, pkg_name)

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
        return self._get_global_list("defines")

    @property
    def cflags(self):
        return self._get_global_list("cflags")

    @property
    def cxxflags(self):
        return self._get_global_list("cxxflags")

    @property
    def sharedlinkflags(self):
        return self._get_global_list("sharedlinkflags")

    @property
    def exelinkflags(self):
        return self._get_global_list("exelinkflags")

    @property
    def sysroot(self):
        # FIXME: Makes no sense
        return self.rootpath

    @property
    def rootpath(self):
        # FIXME: Makes no sense
        if self.rootpaths:
            return self.rootpaths[-1]
        return ""

    @property
    def rootpaths(self):
        result = []
        for dep_cpp_info in self._dependencies.values():
            result.append(dep_cpp_info.rootpath)
        return result

    def _get_global_list(self, name):
        result = []
        for dep_cpp_info in self._dependencies.values():
            for item in getattr(dep_cpp_info, name, []):
                if item not in result:
                    result.append(item)
        return result
