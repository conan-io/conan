import os
from collections import OrderedDict

from conans.errors import ConanException

DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"
DEFAULT_SHARE = "share"
DEFAULT_BUILD = ""


class Component(object):
    """
    Component of a package representing a library or an executable. User can fill all the
    information related to the component
    """

    def __init__(self, name, root_folder):
        self._rootpath = root_folder
        self._name = name
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
        self.cxxflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []
        self.filter_empty = True

    def as_dict(self):
        result = {}
        for name in ["name", "rootpath", "deps", "lib", "exe", "system_deps",
                     "includedirs", "srcdirs", "libdirs", "bindirs", "builddirs", "resdirs",
                     "defines", "cflags", "cxxflags", "sharedlinkflags", "exelinkflags"]:
            result[name] = getattr(self, name)
        return result

    @property
    def name(self):
        return self._name

    @property
    def rootpath(self):
        return self._rootpath

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


class DepComponent(object):
    """
    Component of a package representing a library or an executable. User cannot change the content
    but can check all the information related to the component
    """

    def __init__(self, component):
        self._rootpath = component.rootpath
        self._name = component.name
        self._deps = component.deps
        self._lib = component.lib
        self._exe = component.exe
        self._system_deps = component.system_deps
        self._includedirs = component.includedirs
        self._libdirs = component.libdirs
        self._resdirs = component.resdirs
        self._bindirs = component.bindirs
        self._builddirs = component.builddirs
        self._srcdirs = component.srcdirs
        self._defines = component.defines
        self._cflags = component.cflags
        self._cxxflags = component.cxxflags
        self._sharedlinkflags = component.sharedlinkflags
        self._exelinkflags = component.exelinkflags
        self._filter_empty = component.filter_empty

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self._rootpath, p) for p in paths]
        if self._filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    @property
    def name(self):
        return self._name

    @property
    def rootpath(self):
        return self._rootpath

    @property
    def deps(self):
        return self._deps

    @property
    def lib(self):
        return self._lib

    @property
    def exe(self):
        return self._exe

    @property
    def system_deps(self):
        return self._system_deps

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
        return self._filter_paths(self._includedirs)

    @property
    def lib_paths(self):
        return self._filter_paths(self._libdirs)

    @property
    def bin_paths(self):
        return self._filter_paths(self._bindirs)

    @property
    def build_paths(self):
        return self._filter_paths(self._builddirs)

    @property
    def res_paths(self):
        return self._filter_paths(self._resdirs)

    @property
    def src_paths(self):
        return self._filter_paths(self._srcdirs)

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

    def as_dict(self):
        result = {}
        for name in ["name", "rootpath", "deps", "lib", "exe", "system_deps",
                     "includedirs", "srcdirs", "libdirs", "bindirs", "builddirs", "resdirs",
                     "include_paths", "src_paths", "lib_paths", "bin_paths", "build_paths", "res_paths",
                     "defines", "cflags", "cxxflags", "sharedlinkflags", "exelinkflags"]:
            result[name] = getattr(self, name)
        return result
