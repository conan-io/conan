import copy
import os
from collections import OrderedDict

from conans.errors import ConanException
from conans.model.build_info import DefaultOrderedDict

_DIRS_VAR_NAMES = ["includedirs", "srcdirs", "libdirs", "resdirs", "bindirs", "builddirs",
                  "frameworkdirs"]
_FIELD_VAR_NAMES = ["system_libs", "frameworks", "libs", "defines", "cflags", "cxxflags",
                   "sharedlinkflags", "exelinkflags"]


class _BaseNewCppInfo(object):

    def __init__(self):
        self.names = {}
        self.build_modules = {}

        # ###### DIRECTORIES
        self.includedirs = []  # Ordered list of include paths
        self.srcdirs = []  # Ordered list of source paths
        self.libdirs = []  # Directories to find libraries
        self.resdirs = []  # Directories to find resources, data, etc
        self.bindirs = []  # Directories to find executables and shared libs
        self.builddirs = []
        self.frameworkdirs = []

        # ##### FIELDS
        self.system_libs = []  # Ordered list of system libraries
        self.frameworks = []  # Macos .framework
        self.libs = []  # The libs to link against
        self.defines = []  # preprocessor definitions
        self.cflags = []  # pure C flags
        self.cxxflags = []  # C++ compilation flags
        self.sharedlinkflags = []  # linker flags
        self.exelinkflags = []  # linker flags

        self.sysroot = ""
        self.requires = []

        # ##### PATTERNS
        self.include_patterns = []
        self.lib_patterns = []
        self.bin_patterns = []
        self.src_patterns = []
        self.build_patterns = []
        self.res_patterns = []
        self.framework_patterns = []

    def get_name(self, generator):
        return self.names.get(generator)

    def to_absolute_paths(self, root_folder):
        for name in _DIRS_VAR_NAMES:
            setattr(self, name, [os.path.join(root_folder, c) for c in getattr(self, name)])

        self.build_modules = {k: [os.path.join(root_folder, e) for e in v]
                                  for k, v in self.build_modules.items()}


class NewCppInfo(_BaseNewCppInfo):

    def __init__(self):
        super(NewCppInfo, self).__init__()
        # name of filename to create for various generators.
        # To be used in find package where the filename and the name are not
        # the same
        self.filenames = {}
        self.components = DefaultOrderedDict(lambda: NewComponent())

    @staticmethod
    def from_old_cppinfo(old):
        ret = NewCppInfo()
        for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
            setattr(ret, varname, getattr(old, varname))
        ret.filenames = copy.copy(old.filenames)
        ret.names = copy.copy(old.names)

        # COMPONENTS
        for cname, c in old.components.items():
            for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                setattr(ret.components[cname], varname, getattr(c, varname))
            ret.components[cname].requires = c.requires
            ret.components[cname].names = c.names
        return ret

    def get_sorted_components(self):
        """Order the components taking into account if they depend on another component in the
        same package (not scoped with ::). First less dependant
        return:  {component_name: component}
        """
        processed = []  # Names of the components ordered
        # FIXME: Cache the sort
        while len(self.components) > len(processed):
            for name, c in self.components.items():
                req_processed = [n for n in c.required_component_names if n not in processed]
                if not req_processed and name not in processed:
                    processed.append(name)

        return OrderedDict([(cname,  self.components[cname]) for cname in processed])

    def aggregate_components(self):
        """Aggregates all the components as global values"""
        if self.components:
            components = self.get_sorted_components()
            cnames = list(components.keys())
            cnames.reverse()  # More dependant first

            # Clean global values
            for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                setattr(self, n, [])

            for name in cnames:
                component = components[name]
                for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                    dest = getattr(self, n)
                    dest += [i for i in getattr(component, n) if i not in dest]
                self.requires.extend(component.requires)
            # FIXME: What to do about sysroot?
        self.components = DefaultOrderedDict(lambda: NewComponent())

    def merge(self, other):
        # TODO: Still not used, to be used by global generators
        # If we are merging isolated cppinfo objects is because the generator is "global"
        # (dirs and flags in link order in a single list) so first call
        # cpp_info.aggregate_components()
        if self.components  or other.components:
            raise ConanException("Cannot aggregate two cppinfo objects with components. "
                                 "Do cpp_info.aggregate_components() first")
        for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
            dest = getattr(self, n)
            dest += [i for i in getattr(other, n) if i not in dest]

    def get_filename(self, generator):
        return self.filenames.get(generator) or self.get_name(generator)

    def copy(self):
        ret = copy.copy(self)
        ret.components = DefaultOrderedDict(lambda: NewComponent())
        for comp_name in self.components:
            ret.components[comp_name] = copy.copy(self.components[comp_name])
        return ret

    def to_absolute_paths(self, root_folder):
        super(NewCppInfo, self).to_absolute_paths(root_folder)
        for comp in self.components.values():
            comp.to_absolute_paths(root_folder)

    @property
    def required_components(self):
        """Returns a list of tuples with (require, component_name) required by the package
        If the require is internal (to another component), the require will be None"""
        # FIXME: Cache the value
        ret = [r.split("::") for r in self.requires if "::" in r]
        ret.extend([(None, r) for r in self.requires if "::" not in r and r not in ret])
        for comp in self.components.values():
            ret.extend([r.split("::") for r in comp.requires if "::" in r and r not in ret])
            ret.extend([(None, r) for r in comp.requires if "::" not in r and r not in ret])
        return ret


class NewComponent(_BaseNewCppInfo):

    def __init__(self):
        super(NewComponent, self).__init__()
        self.requires = []

    @property
    def required_component_names(self):
        """ Names of the required components of the same package (not scoped with ::)"""
        return [r for r in self.requires if "::" not in r]
