import os
from collections import OrderedDict
from copy import copy

from conans.errors import ConanException
from conans.util.conan_v2_mode import conan_v2_error

DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"
DEFAULT_SHARE = "share"
DEFAULT_BUILD = ""
DEFAULT_FRAMEWORK = "Frameworks"

COMPONENT_SCOPE = "::"


class DefaultOrderedDict(OrderedDict):

    def __init__(self, factory):
        self.factory = factory
        super(DefaultOrderedDict, self).__init__()

    def __getitem__(self, key):
        if key not in self.keys():
            super(DefaultOrderedDict, self).__setitem__(key, self.factory())
            super(DefaultOrderedDict, self).__getitem__(key).name = key
        return super(DefaultOrderedDict, self).__getitem__(key)

    def __copy__(self):
        the_copy = DefaultOrderedDict(self.factory)
        for key, value in super(DefaultOrderedDict, self).items():
            the_copy[key] = value
        return the_copy


class BuildModulesDict(dict):
    """
    A dictionary with append and extend for cmake build modules to keep it backwards compatible
    with the list interface
    """

    def __getitem__(self, key):
        if key not in self.keys():
            super(BuildModulesDict, self).__setitem__(key, list())
        return super(BuildModulesDict, self).__getitem__(key)

    def _append(self, item):
        if item.endswith(".cmake"):
            self["cmake"].append(item)
            self["cmake_multi"].append(item)
            self["cmake_find_package"].append(item)
            self["cmake_find_package_multi"].append(item)

    def append(self, item):
        conan_v2_error("Use 'self.cpp_info.build_modules[\"<generator>\"].append(\"{item}\")' "
                       'instead'.format(item=item))
        self._append(item)

    def extend(self, items):
        conan_v2_error("Use 'self.cpp_info.build_modules[\"<generator>\"].extend({items})' "
                       "instead".format(items=items))
        for item in items:
            self._append(item)

    @classmethod
    def from_list(cls, build_modules):
        the_dict = BuildModulesDict()
        the_dict.extend(build_modules)
        return the_dict


def dict_to_abs_paths(the_dict, rootpath):
    new_dict = {}
    for generator, values in the_dict.items():
        new_dict[generator] = [os.path.join(rootpath, p) if not os.path.isabs(p) else p
                               for p in values]
    return new_dict


def merge_lists(seq1, seq2):
    return seq1 + [s for s in seq2 if s not in seq1]


def merge_dicts(d1, d2):
    def merge_lists(seq1, seq2):
        return [s for s in seq1 if s not in seq2] + seq2

    result = d1.copy()
    for k, v in d2.items():
        if k not in d1.keys():
            result[k] = v
        else:
            result[k] = merge_lists(d1[k], d2[k])
    return result


class _CppInfo(object):
    """ Object that stores all the necessary information to build in C/C++.
    It is intended to be system independent, translation to
    specific systems will be produced from this info
    """

    def __init__(self):
        self._name = None
        self._generator_properties = {}
        self.names = {}
        self.system_libs = []  # Ordered list of system libraries
        self.includedirs = []  # Ordered list of include paths
        self.srcdirs = []  # Ordered list of source paths
        self.libdirs = []  # Directories to find libraries
        self.resdirs = []  # Directories to find resources, data, etc
        self.bindirs = []  # Directories to find executables and shared libs
        self.builddirs = []
        self.frameworks = []  # Macos .framework
        self.frameworkdirs = []
        self.rootpaths = []
        self.libs = []  # The libs to link against
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cxxflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags
        self.build_modules = BuildModulesDict()  # FIXME: This should be just a plain dict
        self.filenames = {}  # name of filename to create for various generators
        self.rootpath = ""
        self.sysroot = ""
        self.requires = []
        self._build_modules_paths = None
        self._build_modules = None
        self._include_paths = None
        self._lib_paths = None
        self._bin_paths = None
        self._build_paths = None
        self._res_paths = None
        self._src_paths = None
        self._framework_paths = None
        self.version = None  # Version of the conan package
        self.description = None  # Description of the conan package
        # When package is editable, filter_empty=False, so empty dirs are maintained
        self.filter_empty = True

    def _filter_paths(self, paths):
        abs_paths = [os.path.join(self.rootpath, p)
                     if not os.path.isabs(p) else p for p in paths]
        if self.filter_empty:
            return [p for p in abs_paths if os.path.isdir(p)]
        else:
            return abs_paths

    @property
    def build_modules_paths(self):
        if self._build_modules_paths is None:
            if isinstance(self.build_modules, list):  # FIXME: This should be just a plain dict
                conan_v2_error("Use 'self.cpp_info.build_modules[\"<generator>\"] = "
                               "{the_list}' instead".format(the_list=self.build_modules))
                self.build_modules = BuildModulesDict.from_list(self.build_modules)
                # Invalidate necessary, get_build_modules used raise_incorrect_components_definition
                self._build_modules = None
            tmp = dict_to_abs_paths(BuildModulesDict(self.get_build_modules()), self.rootpath)
            self._build_modules_paths = tmp
        return self._build_modules_paths

    @property
    def include_paths(self):
        if self._include_paths is None:
            self._include_paths = self._filter_paths(self.includedirs)
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

    @property
    def framework_paths(self):
        if self._framework_paths is None:
            self._framework_paths = self._filter_paths(self.frameworkdirs)
        return self._framework_paths

    @property
    def name(self):
        conan_v2_error("Use 'get_name(generator)' instead")
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    # TODO: Deprecate for 2.0. Only cmake and pkg_config generators should access this.
    #  Use get_property for 2.0
    def get_name(self, generator, default_name=True):
        property_name = None
        if "cmake" in generator:
            property_name = "cmake_target_name"
        elif "pkg_config" in generator:
            property_name = "pkg_config_name"
        return self.get_property(property_name, generator) \
               or self.names.get(generator, self._name if default_name else None)

    # TODO: Deprecate for 2.0. Only cmake generators should access this. Use get_property for 2.0
    def get_filename(self, generator, default_name=True):
        result = self.get_property("cmake_file_name", generator) or self.filenames.get(generator)
        if result:
            return result
        return self.get_name(generator, default_name=default_name)

    # TODO: Deprecate for 2.0. Use get_property for 2.0
    def get_build_modules(self):
        if self._build_modules is None:  # Not cached yet
            try:
                default_build_modules_value = self._generator_properties[None]["cmake_build_modules"]
            except KeyError:
                ret_dict = {}
            else:
                ret_dict = {"cmake_find_package": default_build_modules_value,
                            "cmake_find_package_multi": default_build_modules_value,
                            "cmake": default_build_modules_value,
                            "cmake_multi": default_build_modules_value}

            for generator, values in self._generator_properties.items():
                if generator:
                    v = values.get("cmake_build_modules")
                    if v:
                        ret_dict[generator] = v
            self._build_modules = ret_dict if ret_dict else self.build_modules
        return self._build_modules

    def set_property(self, property_name, value, generator=None):
        self._generator_properties.setdefault(generator, {})[property_name] = value

    def get_property(self, property_name, generator=None):
        if generator:
            try:
                return self._generator_properties[generator][property_name]
            except KeyError:
                pass
        try:
            return self._generator_properties[None][property_name]
        except KeyError:
            pass


class Component(_CppInfo):

    def __init__(self, rootpath, version, default_values):
        super(Component, self).__init__()
        self.rootpath = rootpath
        if default_values.includedir is not None:
            self.includedirs.append(default_values.includedir)
        if default_values.libdir is not None:
            self.libdirs.append(default_values.libdir)
        if default_values.bindir is not None:
            self.bindirs.append(default_values.bindir)
        if default_values.resdir is not None:
            self.resdirs.append(default_values.resdir)
        if default_values.builddir is not None:
            self.builddirs.append(default_values.builddir)
        if default_values.frameworkdir is not None:
            self.frameworkdirs.append(default_values.frameworkdir)
        self.requires = []
        self.version = version


class CppInfoDefaultValues(object):

    def __init__(self, includedir=None, libdir=None, bindir=None,
                 resdir=None, builddir=None, frameworkdir=None):
        self.includedir = includedir
        self.libdir = libdir
        self.bindir = bindir
        self.resdir = resdir
        self.builddir = builddir
        self.frameworkdir = frameworkdir


class CppInfo(_CppInfo):
    """ Build Information declared to be used by the CONSUMERS of a
    conans. That means that consumers must use this flags and configs i order
    to build properly.
    Defined in user CONANFILE, directories are relative at user definition time
    """

    def __init__(self, ref_name, root_folder, default_values=None):
        super(CppInfo, self).__init__()
        self._ref_name = ref_name
        self._name = ref_name
        self.rootpath = root_folder  # the full path of the package in which the conans is found
        self._default_values = default_values or CppInfoDefaultValues(DEFAULT_INCLUDE, DEFAULT_LIB,
                                                                      DEFAULT_BIN, DEFAULT_RES,
                                                                      DEFAULT_BUILD,
                                                                      DEFAULT_FRAMEWORK)
        if self._default_values.includedir is not None:
            self.includedirs.append(self._default_values.includedir)
        if self._default_values.libdir is not None:
            self.libdirs.append(self._default_values.libdir)
        if self._default_values.bindir is not None:
            self.bindirs.append(self._default_values.bindir)
        if self._default_values.resdir is not None:
            self.resdirs.append(self._default_values.resdir)
        if self._default_values.builddir is not None:
            self.builddirs.append(self._default_values.builddir)
        if self._default_values.frameworkdir is not None:
            self.frameworkdirs.append(self._default_values.frameworkdir)
        self.components = DefaultOrderedDict(lambda: Component(self.rootpath,
                                                               self.version, self._default_values))
        self._configs = {}

    def __str__(self):
        return self._ref_name

    def get_name(self, generator, default_name=True):
        name = super(CppInfo, self).get_name(generator, default_name=default_name)
        return name

    @property
    def configs(self):
        return self._configs

    def __getattr__(self, config):
        def _get_cpp_info():
            result = _CppInfo()
            result.filter_empty = self.filter_empty
            result.rootpath = self.rootpath
            result.sysroot = self.sysroot
            result.includedirs.append(self._default_values.includedir)
            result.libdirs.append(self._default_values.libdir)
            result.bindirs.append(self._default_values.bindir)
            result.resdirs.append(self._default_values.resdir)
            result.builddirs.append(self._default_values.builddir)
            result.frameworkdirs.append(self._default_values.frameworkdir)
            return result

        return self._configs.setdefault(config, _get_cpp_info())

    def _raise_incorrect_components_definition(self, package_name, package_requires):
        if not self.components and not self.requires:
            return

        # Raise if mixing components
        if self.components and \
            (self.includedirs != ([self._default_values.includedir]
                if self._default_values.includedir is not None else []) or
             self.libdirs != ([self._default_values.libdir]
                if self._default_values.libdir is not None else []) or
             self.bindirs != ([self._default_values.bindir]
                if self._default_values.bindir is not None else []) or
             self.resdirs != ([self._default_values.resdir]
                if self._default_values.resdir is not None else []) or
             self.builddirs != ([self._default_values.builddir]
                if self._default_values.builddir is not None else []) or
             self.frameworkdirs != ([self._default_values.frameworkdir]
                if self._default_values.frameworkdir is not None  else []) or
             self.libs or
             self.system_libs or
             self.frameworks or
             self.defines or
             self.cflags or
             self.cxxflags or
             self.sharedlinkflags or
             self.exelinkflags or
             self.get_build_modules() or
             self.requires):
            raise ConanException("self.cpp_info.components cannot be used with self.cpp_info "
                                 "global values at the same time")
        if self._configs:
            raise ConanException("self.cpp_info.components cannot be used with self.cpp_info configs"
                                 " (release/debug/...) at the same time")

        pkg_requires = [require.ref.name for require in package_requires.values()]

        def _check_components_requires_instersection(comp_requires):
            reqs = [it.split(COMPONENT_SCOPE)[0] for it in comp_requires if COMPONENT_SCOPE in it]
            # Raise on components requires without package requires
            for pkg_require in pkg_requires:
                if package_requires[pkg_require].private or package_requires[pkg_require].override:
                    # Not standard requires, skip
                    continue
                if pkg_require not in reqs:
                    raise ConanException("Package require '%s' not used in components requires"
                                         % pkg_require)
            # Raise on components requires requiring inexistent package requires
            for comp_require in reqs:
                reason = None
                if comp_require not in pkg_requires:
                    reason = "not defined as a recipe requirement"
                elif package_requires[comp_require].private and package_requires[
                    comp_require].override:
                    reason = "it was defined as an overridden private recipe requirement"
                elif package_requires[comp_require].private:
                    reason = "it was defined as a private recipe requirement"
                elif package_requires[comp_require].override:
                    reason = "it was defined as an overridden recipe requirement"

                if reason is not None:
                    raise ConanException("Package require '%s' declared in components requires "
                                         "but %s" % (comp_require, reason))

        if self.components:
            # Raise on component name
            for comp_name, comp in self.components.items():
                if comp_name == package_name:
                    raise ConanException(
                        "Component name cannot be the same as the package name: '%s'"
                        % comp_name)

            # check that requires are used in components and check that components exists in requires
            requires_from_components = set()
            for comp_name, comp in self.components.items():
                requires_from_components.update(comp.requires)

            _check_components_requires_instersection(requires_from_components)
        else:
            _check_components_requires_instersection(self.requires)
