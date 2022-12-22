import copy
import os
from collections import OrderedDict

from conan.api.output import ConanOutput
from conans.errors import ConanException

_DIRS_VAR_NAMES = ["_includedirs", "_srcdirs", "_libdirs", "_resdirs", "_bindirs", "_builddirs",
                   "_frameworkdirs", "_objects"]
_FIELD_VAR_NAMES = ["_system_libs", "_frameworks", "_libs", "_defines", "_cflags", "_cxxflags",
                    "_sharedlinkflags", "_exelinkflags"]
_ALL_NAMES = _DIRS_VAR_NAMES + _FIELD_VAR_NAMES


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


class MockInfoProperty(object):
    """
    # TODO: Remove in 2.X
    to mock user_info and env_info
    """
    def __init__(self, name):
        self._message = f"The use of '{name}' is deprecated in Conan 2.0 and will be removed in " \
                        f"Conan 2.X. Please, update your recipes unless you are maintaining " \
                        f"compatibility with Conan 1.X"

    def __getitem__(self, key):
        ConanOutput().warning(self._message)
        return []

    def __setitem__(self, key, value):
        ConanOutput().warning(self._message)

    def __getattr__(self, attr):
        if attr != "_message":
            ConanOutput().warning(self._message)
        return []

    def __setattr__(self, attr, value):
        if attr != "_message":
            ConanOutput().warning(self._message)
        return super(MockInfoProperty, self).__setattr__(attr, value)


class _Component(object):

    def __init__(self, set_defaults=False):
        # ###### PROPERTIES
        self._generator_properties = None

        # ###### DIRECTORIES
        self._includedirs = None  # Ordered list of include paths
        self._srcdirs = None  # Ordered list of source paths
        self._libdirs = None  # Directories to find libraries
        self._resdirs = None  # Directories to find resources, data, etc
        self._bindirs = None  # Directories to find executables and shared libs
        self._builddirs = None
        self._frameworkdirs = None

        # ##### FIELDS
        self._system_libs = None  # Ordered list of system libraries
        self._frameworks = None  # Macos .framework
        self._libs = None  # The libs to link against
        self._defines = None  # preprocessor definitions
        self._cflags = None  # pure C flags
        self._cxxflags = None  # C++ compilation flags
        self._sharedlinkflags = None  # linker flags
        self._exelinkflags = None  # linker flags
        self._objects = None  # linker flags

        self._sysroot = None
        self._requires = None

        # LEGACY 1.X fields, can be removed in 2.X
        self.names = MockInfoProperty("cpp_info.names")
        self.filenames = MockInfoProperty("cpp_info.filenames")
        self.build_modules = MockInfoProperty("cpp_info.build_modules")

        if set_defaults:
            self.includedirs = ["include"]
            self.libdirs = ["lib"]
            self.bindirs = ["bin"]

    def serialize(self):
        return {
            "includedirs": self._includedirs,
            "srcdirs": self._srcdirs,
            "libdirs": self._libdirs,
            "resdirs": self._resdirs,
            "bindirs": self._bindirs,
            "builddirs": self._builddirs,
            "frameworkdirs": self._frameworkdirs,
            "system_libs": self._system_libs,
            "frameworks": self._frameworks,
            "libs": self._libs,
            "defines": self._defines,
            "cflags": self._cflags,
            "cxxflags": self._cxxflags,
            "sharedlinkflags": self._sharedlinkflags,
            "exelinkflags": self._exelinkflags,
            "objects": self._objects,
            "sysroot": self._sysroot,
            "requires": self._requires,
            "properties": self._generator_properties
        }

    @property
    def includedirs(self):
        if self._includedirs is None:
            self._includedirs = []
        return self._includedirs

    @includedirs.setter
    def includedirs(self, value):
        self._includedirs = value

    @property
    def srcdirs(self):
        if self._srcdirs is None:
            self._srcdirs = []
        return self._srcdirs

    @srcdirs.setter
    def srcdirs(self, value):
        self._srcdirs = value

    @property
    def libdirs(self):
        if self._libdirs is None:
            self._libdirs = []
        return self._libdirs

    @libdirs.setter
    def libdirs(self, value):
        self._libdirs = value

    @property
    def resdirs(self):
        if self._resdirs is None:
            self._resdirs = []
        return self._resdirs

    @resdirs.setter
    def resdirs(self, value):
        self._resdirs = value

    @property
    def bindirs(self):
        if self._bindirs is None:
            self._bindirs = []
        return self._bindirs

    @bindirs.setter
    def bindirs(self, value):
        self._bindirs = value

    @property
    def builddirs(self):
        if self._builddirs is None:
            self._builddirs = []
        return self._builddirs

    @builddirs.setter
    def builddirs(self, value):
        self._builddirs = value

    @property
    def frameworkdirs(self):
        if self._frameworkdirs is None:
            self._frameworkdirs = []
        return self._frameworkdirs

    @frameworkdirs.setter
    def frameworkdirs(self, value):
        self._frameworkdirs = value

    @property
    def bindir(self):
        bindirs = self.bindirs
        assert bindirs
        assert len(bindirs) == 1
        return bindirs[0]

    @property
    def libdir(self):
        libdirs = self.libdirs
        assert libdirs
        assert len(libdirs) == 1
        return libdirs[0]

    @property
    def includedir(self):
        includedirs = self.includedirs
        assert includedirs
        assert len(includedirs) == 1
        return includedirs[0]

    @property
    def system_libs(self):
        if self._system_libs is None:
            self._system_libs = []
        return self._system_libs

    @system_libs.setter
    def system_libs(self, value):
        self._system_libs = value

    @property
    def frameworks(self):
        if self._frameworks is None:
            self._frameworks = []
        return self._frameworks

    @frameworks.setter
    def frameworks(self, value):
        self._frameworks = value

    @property
    def libs(self):
        if self._libs is None:
            self._libs = []
        return self._libs

    @libs.setter
    def libs(self, value):
        self._libs = value

    @property
    def defines(self):
        if self._defines is None:
            self._defines = []
        return self._defines

    @defines.setter
    def defines(self, value):
        self._defines = value

    @property
    def cflags(self):
        if self._cflags is None:
            self._cflags = []
        return self._cflags

    @cflags.setter
    def cflags(self, value):
        self._cflags = value

    @property
    def cxxflags(self):
        if self._cxxflags is None:
            self._cxxflags = []
        return self._cxxflags

    @cxxflags.setter
    def cxxflags(self, value):
        self._cxxflags = value

    @property
    def sharedlinkflags(self):
        if self._sharedlinkflags is None:
            self._sharedlinkflags = []
        return self._sharedlinkflags

    @sharedlinkflags.setter
    def sharedlinkflags(self, value):
        self._sharedlinkflags = value

    @property
    def exelinkflags(self):
        if self._exelinkflags is None:
            self._exelinkflags = []
        return self._exelinkflags

    @exelinkflags.setter
    def exelinkflags(self, value):
        self._exelinkflags = value

    @property
    def objects(self):
        if self._objects is None:
            self._objects = []
        return self._objects

    @objects.setter
    def objects(self, value):
        self._objects = value

    @property
    def sysroot(self):
        if self._sysroot is None:
            self._sysroot = ""
        return self._sysroot

    @sysroot.setter
    def sysroot(self, value):
        self._sysroot = value

    @property
    def requires(self):
        if self._requires is None:
            self._requires = []
        return self._requires

    @requires.setter
    def requires(self, value):
        self._requires = value

    @property
    def required_component_names(self):
        """ Names of the required components of the same package (not scoped with ::)"""
        if self.requires is None:
            return []
        return [r for r in self.requires if "::" not in r]

    def set_property(self, property_name, value):
        if self._generator_properties is None:
            self._generator_properties = {}
        self._generator_properties[property_name] = value

    def get_property(self, property_name):
        if self._generator_properties is None:
            return None
        try:
            return self._generator_properties[property_name]
        except KeyError:
            pass

    def get_init(self, attribute, default):
        item = getattr(self, attribute)
        if item is not None:
            return item
        setattr(self, attribute, default)
        return default


class CppInfo(object):

    def __init__(self, set_defaults=False):
        self.components = DefaultOrderedDict(lambda: _Component(set_defaults))
        # Main package is a component with None key
        self.components[None] = _Component(set_defaults)
        self._aggregated = None  # A _NewComponent object with all the components aggregated

    def __getattr__(self, attr):
        return getattr(self.components[None], attr)

    def __setattr__(self, attr, value):
        if attr == "components":
            super(CppInfo, self).__setattr__(attr, value)
        else:
            setattr(self.components[None], attr, value)

    def serialize(self):
        ret = {}
        for component_name, info in self.components.items():
            _name = "root" if component_name is None else component_name
            ret[_name] = info.serialize()
        return ret

    @property
    def has_components(self):
        return len(self.components) > 1

    @property
    def component_names(self):
        return filter(None, self.components.keys())

    def merge(self, other, overwrite=False):
        """Merge 'other' into self. 'other' can be an old cpp_info object
        Used to merge Layout source + build cpp objects info (editables)
        :type other: CppInfo
        """

        def merge_list(o, d):
            d.extend(e for e in o if e not in d)

        for varname in _ALL_NAMES:
            other_values = getattr(other, varname)
            if other_values is not None:
                if not overwrite:
                    current_values = self.components[None].get_init(varname, [])
                    merge_list(other_values, current_values)
                else:
                    setattr(self, varname, other_values)
        if not self.sysroot and other.sysroot:
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
            for varname in _ALL_NAMES:
                other_values = getattr(c, varname)
                if other_values is not None:
                    if not overwrite:
                        current_values = self.components[cname].get_init(varname, [])
                        merge_list(other_values, current_values)
                    else:
                        setattr(self.components[cname], varname, other_values)
            if c.requires:
                current_values = self.components[cname].get_init("requires", [])
                merge_list(c.requires, current_values)

            if c._generator_properties:
                current_values = self.components[cname].get_init("_generator_properties", {})
                current_values.update(c._generator_properties)

    def set_relative_base_folder(self, folder):
        """Prepend the folder to all the directories"""
        for component in self.components.values():
            for varname in _DIRS_VAR_NAMES:
                origin = getattr(component, varname)
                if origin is not None:
                    origin[:] = [os.path.join(folder, el) for el in origin]
            if component._generator_properties is not None:
                updates = {}
                for prop_name, value in component._generator_properties.items():
                    if prop_name == "cmake_build_modules":
                        if isinstance(value, list):
                            updates[prop_name] = [os.path.join(folder, v) for v in value]
                        else:
                            updates[prop_name] = os.path.join(folder, value)
                component._generator_properties.update(updates)

    def deploy_base_folder(self, package_folder, deploy_folder):
        """Prepend the folder to all the directories"""
        for component in self.components.values():
            for varname in _DIRS_VAR_NAMES:
                origin = getattr(component, varname)
                if origin is not None:
                    new_ = []
                    for el in origin:
                        rel_path = os.path.relpath(el, package_folder)
                        new_.append(os.path.join(deploy_folder, rel_path))
                    origin[:] = new_
                # TODO: Missing properties

    def _raise_circle_components_requires_error(self):
        """
        Raise an exception because of a requirements loop detection in components.
        The exception message gives some information about the involved components.
        """
        deps_set = set()
        for comp_name, comp in self.components.items():
            for dep_name, dep in self.components.items():
                for require in dep.required_component_names:
                    if require == comp_name:
                        deps_set.add("   {} requires {}".format(dep_name, comp_name))
        dep_mesg = "\n".join(deps_set)
        raise ConanException(f"There is a dependency loop in "
                             f"'self.cpp_info.components' requires:\n{dep_mesg}")

    def get_sorted_components(self):
        """
        Order the components taking into account if they depend on another component in the
        same package (not scoped with ::). First less dependant.

        :return: ``OrderedDict`` {component_name: component}
        """
        processed = []  # Names of the components ordered
        # FIXME: Cache the sort
        while (len(self.components) - 1) > len(processed):
            cached_processed = processed[:]
            for name, c in self.components.items():
                if name is None:
                    continue
                req_processed = [n for n in c.required_component_names if n not in processed]
                if not req_processed and name not in processed:
                    processed.append(name)
            # If cached_processed did not change then detected cycle components requirements!
            if cached_processed == processed:
                self._raise_circle_components_requires_error()

        return OrderedDict([(cname, self.components[cname]) for cname in processed])

    def aggregated_components(self):
        """Aggregates all the components as global values, returning a new CppInfo"""
        if self._aggregated is None:
            if self.has_components:
                result = _Component()
                for n in _ALL_NAMES:  # Initialize all values, from None => []
                    setattr(result, n, [])  # TODO: This is a bit dirty
                # Reversed to make more dependant first
                for name, component in reversed(self.get_sorted_components().items()):
                    for n in _ALL_NAMES:
                        if getattr(component, n):
                            dest = result.get_init(n, [])
                            dest.extend([i for i in getattr(component, n) if i not in dest])

                    # NOTE: The properties are not aggregated because they might refer only to the
                    # component like "cmake_target_name" describing the target name FOR THE component
                    # not the namespace.
                    if component.requires:
                        current_values = result.get_init("requires", [])
                        current_values.extend(component.requires)

                # FIXME: What to do about sysroot?
                result._generator_properties = copy.copy(self._generator_properties)
            else:
                result = copy.copy(self.components[None])
            self._aggregated = CppInfo()
            self._aggregated.components[None] = result
        return self._aggregated

    def check_component_requires(self, conanfile):
        """ quality check for component requires:
        - Check that all recipe ``requires`` are used if consumer recipe explicit opt-in to use
          component requires
        - Check that component external dep::comp dependency "dep" is a recipe "requires"
        - Check that every internal component require actually exist
        It doesn't check that external components do exist
        """
        if not self.has_components and not self.requires:
            return
        # Accumulate all external requires
        external = set()
        internal = set()
        # TODO: Cache this, this is computed in different places
        for key, comp in self.components.items():
            external.update(r.split("::")[0] for r in comp.requires if "::" in r)
            internal.update(r for r in comp.requires if "::" not in r)

        missing_internal = list(internal.difference(self.components))
        if missing_internal:
            raise ConanException(f"{conanfile}: Internal components not found: {missing_internal}")
        if not external:
            return
        # Only direct host dependencies can be used with components
        direct_dependencies = [d.ref.name
                               for d, _ in conanfile.dependencies.filter({"direct": True,
                                                                          "build": False}).items()]
        for e in external:
            if e not in direct_dependencies:
                raise ConanException(
                    f"{conanfile}: required component package '{e}::' not in dependencies")
        for e in direct_dependencies:
            if e not in external:
                raise ConanException(
                    f"{conanfile}: Required package '{e}' not in component 'requires'")

    def copy(self):
        # Only used at the moment by layout() editable merging build+source .cpp data
        ret = CppInfo()
        ret._generator_properties = copy.copy(self._generator_properties)
        ret.components = DefaultOrderedDict(lambda: _Component())
        for comp_name in self.components:
            ret.components[comp_name] = copy.copy(self.components[comp_name])
        return ret

    @property
    def required_components(self):
        """Returns a list of tuples with (require, component_name) required by the package
        If the require is internal (to another component), the require will be None"""
        # FIXME: Cache the value
        # First aggregate without repetition, respecting the order
        ret = []
        for comp in self.components.values():
            for r in comp.requires:
                if r not in ret:
                    ret.append(r)
        # Then split the names
        ret = [r.split("::") if "::" in r else (None, r) for r in ret]
        return ret

    def __str__(self):
        ret = []
        for cname, c in self.components.items():
            for n in _ALL_NAMES:
                ret.append("Component: '{}' "
                           "Var: '{}' "
                           "Value: '{}'".format(cname, n, getattr(c, n)))
        return "\n".join(ret)
