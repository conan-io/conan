import copy
import os
from collections import OrderedDict

from conans.model.build_info import DefaultOrderedDict

_DIRS_VAR_NAMES = ["includedirs", "srcdirs", "libdirs", "resdirs", "bindirs", "builddirs",
                   "frameworkdirs"]
_FIELD_VAR_NAMES = ["system_libs", "frameworks", "libs", "defines", "cflags", "cxxflags",
                    "sharedlinkflags", "exelinkflags", "objects"]


class _NewComponent(object):

    def __init__(self):
        # ###### PROPERTIES
        self._generator_properties = None

        # ###### DIRECTORIES
        self.includedirs = None  # Ordered list of include paths
        self.srcdirs = None  # Ordered list of source paths
        self.libdirs = None  # Directories to find libraries
        self.resdirs = None  # Directories to find resources, data, etc
        self.bindirs = None  # Directories to find executables and shared libs
        self.builddirs = None
        self.frameworkdirs = None

        # ##### FIELDS
        self.system_libs = None  # Ordered list of system libraries
        self.frameworks = None  # Macos .framework
        self.libs = None  # The libs to link against
        self.defines = None  # preprocessor definitions
        self.cflags = None  # pure C flags
        self.cxxflags = None  # C++ compilation flags
        self.sharedlinkflags = None  # linker flags
        self.exelinkflags = None  # linker flags
        self.objects = None  # objects to link

        self.sysroot = None
        self.requires = None

    @property
    def required_component_names(self):
        """ Names of the required components of the same package (not scoped with ::)"""
        if self.requires is None:
            return []
        return [r for r in self.requires if "::" not in r]

    def set_property(self, property_name, value, generator=None):
        if self._generator_properties is None:
            self._generator_properties = {}
        self._generator_properties.setdefault(generator, {})[property_name] = value

    def get_property(self, property_name, generator=None):
        if self._generator_properties is None:
            return None
        if generator:
            try:
                return self._generator_properties[generator][property_name]
            except KeyError:
                pass
        try:  # generator = None is the dict for all generators
            return self._generator_properties[None][property_name]
        except KeyError:
            pass

    def get_init(self, attribute, default):
        item = getattr(self, attribute)
        if item is not None:
            return item
        setattr(self, attribute, default)
        return default


class NewCppInfo(object):

    def __init__(self):
        self.components = DefaultOrderedDict(lambda: _NewComponent())
        # Main package is a component with None key
        self.components[None] = _NewComponent()

    def __getattr__(self, attr):
        return getattr(self.components[None], attr)

    def __setattr__(self, attr, value):
        if attr == "components":
            super(NewCppInfo, self).__setattr__(attr, value)
        else:
            setattr(self.components[None], attr, value)

    @property
    def has_components(self):
        return len(self.components) > 1

    @property
    def component_names(self):
        return filter(None, self.components.keys())

    def merge(self, other):
        """Merge 'other' into self. 'other' can be an old cpp_info object"""
        def merge_list(o, d):
            d.extend(e for e in o if e not in d)

        for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
            other_values = getattr(other, varname)
            if other_values is not None:
                current_values = self.components[None].get_init(varname, [])
                merge_list(other_values, current_values)

        if self.sysroot is None and other.sysroot:
            self.sysroot = other.sysroot

        if other.requires:
            current_values = self.components[None].get_init("requires", [])
            merge_list(other.requires, current_values)

        if other._generator_properties:
            current_values = self.components[None].get_init("_generator_properties", {})
            current_values.update(other._generator_properties)

        # COMPONENTS
        for cname, c in other.components.items():
            if cname is None:
                continue
            for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                other_values = getattr(c, varname)
                if other_values is not None:
                    current_values = self.components[cname].get_init(varname, [])
                    merge_list(other_values, current_values)

            if c.requires:
                current_values = self.components[cname].get_init("requires", [])
                merge_list(c.requires, current_values)

            if c._generator_properties:
                current_values = self.components[cname].get_init("_generator_properties", {})
                current_values.update(c._generator_properties)

    def set_relative_base_folder(self, folder):
        """Prepend the folder to all the directories"""
        for cname, c in self.components.items():
            for varname in _DIRS_VAR_NAMES:
                origin = getattr(self.components[cname], varname)
                if origin is not None:
                    origin[:] = [os.path.join(folder, el) for el in origin]

    def get_sorted_components(self):
        """Order the components taking into account if they depend on another component in the
        same package (not scoped with ::). First less dependant
        return:  {component_name: component}
        """
        processed = []  # Names of the components ordered
        # FIXME: Cache the sort
        while (len(self.components) - 1) > len(processed):
            for name, c in self.components.items():
                if name is None:
                    continue
                req_processed = [n for n in c.required_component_names if n not in processed]
                if not req_processed and name not in processed:
                    processed.append(name)

        return OrderedDict([(cname,  self.components[cname]) for cname in processed])

    def aggregate_components(self):
        """Aggregates all the components as global values"""

        if self.has_components:
            components = self.get_sorted_components()
            cnames = list(components.keys())
            cnames.reverse()  # More dependant first

            # Clean global values
            for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                setattr(self.components[None], n, [])

            for name in cnames:
                component = components[name]
                for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                    if getattr(component, n):
                        dest = getattr(self.components[None], n)
                        if dest is None:
                            setattr(self.components[None], n, [])
                        dest += [i for i in getattr(component, n) if i not in dest]

                # NOTE: The properties are not aggregated because they might refer only to the
                # component like "cmake_target_name" describing the target name FOR THE component
                # not the namespace.

                if component.requires:
                    current_values = self.components[None].get_init("requires", [])
                    current_values.extend(component.requires)

            # FIXME: What to do about sysroot?
            # Leave only the aggregated value
            main_value = self.components[None]
            self.components = DefaultOrderedDict(lambda: _NewComponent())
            self.components[None] = main_value

    def copy(self):
        ret = NewCppInfo()
        ret._generator_properties = copy.copy(self._generator_properties)
        ret.components = DefaultOrderedDict(lambda: _NewComponent())
        for comp_name in self.components:
            ret.components[comp_name] = copy.copy(self.components[comp_name])
        return ret

    @property
    def required_components(self):
        """Returns a list of tuples with (require, component_name) required by the package
        If the require is internal (to another component), the require will be None"""
        # FIXME: Cache the value
        ret = []
        for key, comp in self.components.items():
            ret.extend([r.split("::") for r in comp.requires if "::" in r and r not in ret])
            ret.extend([(None, r) for r in comp.requires if "::" not in r and r not in ret])
        return ret

    def clear_none(self):
        """A field with None meaning is 'not declared' but for consumers, that is irrelevant, an
        empty list is easier to handle and makes perfect sense."""
        for c in self.components.values():
            for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                if getattr(c, varname) is None:
                    setattr(c, varname, [])
            if c.requires is None:
                c.requires = []
        if self.sysroot is None:
            self.sysroot = ""
        if self._generator_properties is None:
            self._generator_properties = {}

    def __str__(self):
        ret = []
        for cname, c in self.components.items():
            for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                ret.append("Component: '{}' "
                           "Var: '{}' "
                           "Value: '{}'".format(cname, n, getattr(c, n)))
        return "\n".join(ret)


def from_old_cppinfo(old):
    ret = NewCppInfo()
    ret.merge(old)
    ret.clear_none()

    def _copy_build_modules_to_property(origin, dest):
        current_value = dest.get_property("cmake_build_modules") or []
        if isinstance(origin.build_modules, list):
            current_value.extend([v for v in origin.build_modules if v not in current_value])
        else:
            multi = origin.build_modules.get("cmake_find_package_multi")
            no_multi = origin.build_modules.get("cmake_find_package")
            if multi:
                current_value.extend([v for v in multi if v not in current_value])
            if no_multi:
                current_value.extend([v for v in no_multi if v not in current_value])
        dest.set_property("cmake_build_modules", current_value)

    # Copy the build modules as the new recommended property
    if old.build_modules:
        _copy_build_modules_to_property(old, ret)

    for cname, c in old.components.items():
        if c.build_modules:
            # The build modules properties are applied to the root cppinfo, not per component
            # because it is something global that makes no sense to be set at a component
            _copy_build_modules_to_property(c, ret)
    return ret


def fill_old_cppinfo(origin, old_cpp):
    """Copy the values from a new cpp info object to an old one but prioritizing it,
    if the value is not None, then override the declared in the conanfile.cpp_info => (dest)"""

    if origin.has_components:
        # If the user declared components, reset the global values
        origin.components[None] = _NewComponent()
        # COMPONENTS
        for cname, c in origin.components.items():
            if cname is None:
                continue
            for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
                value = getattr(c, varname)
                if value is not None:
                    # Override the self.cpp_info component value
                    setattr(old_cpp.components[cname], varname, copy.copy(value))

            if c.requires is not None:
                old_cpp.components[cname].requires = copy.copy(c.requires)
            if c._generator_properties is not None:
                old_cpp.components[cname]._generator_properties = copy.copy(c._generator_properties)
    else:
        for varname in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
            value = getattr(origin, varname)
            if value is not None:
                # Override the self.cpp_info value
                setattr(old_cpp, varname, copy.copy(value))
        if origin._generator_properties is not None:
            old_cpp._generator_properties = copy.copy(origin._generator_properties)
