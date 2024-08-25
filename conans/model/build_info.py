import copy
import json
import os
from collections import OrderedDict, defaultdict

from conan.api.output import ConanOutput
from conans.errors import ConanException
from conans.util.files import load, save

_DIRS_VAR_NAMES = ["_includedirs", "_srcdirs", "_libdirs", "_resdirs", "_bindirs", "_builddirs",
                   "_frameworkdirs", "_objects"]
_FIELD_VAR_NAMES = ["_system_libs", "_frameworks", "_libs", "_defines", "_cflags", "_cxxflags",
                    "_sharedlinkflags", "_exelinkflags"]
_ALL_NAMES = _DIRS_VAR_NAMES + _FIELD_VAR_NAMES


class MockInfoProperty:
    """
    # TODO: Remove in 2.X
    to mock user_info and env_info
    """
    counter = {}
    package = None

    def __init__(self, name):
        self._name = name

    @staticmethod
    def message():
        if not MockInfoProperty.counter:
            return
        ConanOutput().warning("Usage of deprecated Conan 1.X features that will be removed in "
                              "Conan 2.X:", warn_tag="deprecated")
        for k, v in MockInfoProperty.counter.items():
            ConanOutput().warning(f"    '{k}' used in: {', '.join(v)}", warn_tag="deprecated")
        MockInfoProperty.counter = {}

    def __getitem__(self, key):
        MockInfoProperty.counter.setdefault(self._name, set()).add(self.package)
        return []

    def __setitem__(self, key, value):
        MockInfoProperty.counter.setdefault(self._name, set()).add(self.package)

    def __getattr__(self, attr):
        MockInfoProperty.counter.setdefault(self._name, set()).add(self.package)
        return []

    def __setattr__(self, attr, value):
        if attr != "_name":
            MockInfoProperty.counter.setdefault(self._name, set()).add(self.package)
        return super(MockInfoProperty, self).__setattr__(attr, value)


class _Component:

    def __init__(self, set_defaults=False):
        # ###### PROPERTIES
        self._properties = None

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
            "properties": self._properties
        }

    @staticmethod
    def deserialize(contents):
        result = _Component()
        for field, value in contents.items():
            setattr(result, f"_{field}", value)
        return result

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
        if not bindirs or len(bindirs) != 1:
            raise ConanException(f"The bindir property is undefined because bindirs "
                                 f"{'is empty' if not bindirs else 'has more than one element'}."
                                 f" Consider using the bindirs property.")
        return bindirs[0]

    @property
    def libdir(self):
        libdirs = self.libdirs
        if not libdirs or len(libdirs) != 1:
            raise ConanException(f"The libdir property is undefined because libdirs "
                                 f"{'is empty' if not libdirs else 'has more than one element'}."
                                 f" Consider using the libdirs property.")
        return libdirs[0]

    @property
    def includedir(self):
        includedirs = self.includedirs
        if not includedirs or len(includedirs) != 1:
            raise ConanException(f"The includedir property is undefined because includedirs "
                                 f"{'is empty' if not includedirs else 'has more than one element'}."
                                 f" Consider using the includedirs property.")
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
        if isinstance(self._libs, dict):
            return [self._libs.keys()]  # Return a list to not break any interface
        return self._libs

    @property
    def full_libs(self):
        if self._libs is None:
            self._libs = []
        if isinstance(self._libs, list):
            return {k: {} for k in self._libs}
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
        """ Names of the required INTERNAL components of the same package (not scoped with ::)"""
        if self.requires is None:
            return []
        return [r for r in self.requires if "::" not in r]

    def set_property(self, property_name, value):
        if self._properties is None:
            self._properties = {}
        self._properties[property_name] = value

    def get_property(self, property_name, check_type=None):
        if self._properties is None:
            return None
        try:
            value = self._properties[property_name]
            if check_type is not None and not isinstance(value, check_type):
                raise ConanException(
                    f'The expected type for {property_name} is "{check_type.__name__}", but "{type(value).__name__}" was found')
            return value
        except KeyError:
            pass

    def get_init(self, attribute, default):
        # Similar to dict.setdefault
        item = getattr(self, attribute)
        if item is not None:
            return item
        setattr(self, attribute, default)
        return default

    def merge(self, other, overwrite=False):
        """
        @param overwrite:
        @type other: _Component
        """
        def merge_list(o, d):
            d.extend(e for e in o if e not in d)

        for varname in _ALL_NAMES:
            other_values = getattr(other, varname)
            if other_values is not None:
                if not overwrite:
                    current_values = self.get_init(varname, [])
                    merge_list(other_values, current_values)
                else:
                    setattr(self, varname, other_values)

        if other.requires:
            current_values = self.get_init("requires", [])
            merge_list(other.requires, current_values)

        if other._properties:
            current_values = self.get_init("_properties", {})
            current_values.update(other._properties)

    def set_relative_base_folder(self, folder):
        for varname in _DIRS_VAR_NAMES:
            origin = getattr(self, varname)
            if origin is not None:
                origin[:] = [os.path.join(folder, el) for el in origin]
        properties = self._properties
        if properties is not None:
            modules = properties.get("cmake_build_modules")  # Only this prop at this moment
            if modules is not None:
                assert isinstance(modules, list), "cmake_build_modules must be a list"
                properties["cmake_build_modules"] = [os.path.join(folder, v) for v in modules]

    def deploy_base_folder(self, package_folder, deploy_folder):
        def relocate(el):
            rel_path = os.path.relpath(el, package_folder)
            if rel_path.startswith(".."):
                # If it is pointing to a folder outside of the package, then do not relocate
                return el
            return os.path.join(deploy_folder, rel_path)

        for varname in _DIRS_VAR_NAMES:
            origin = getattr(self, varname)
            if origin is not None:
                origin[:] = [relocate(f) for f in origin]
        properties = self._properties
        if properties is not None:
            modules = properties.get("cmake_build_modules")  # Only this prop at this moment
            if modules is not None:
                assert isinstance(modules, list), "cmake_build_modules must be a list"
                properties["cmake_build_modules"] = [relocate(f) for f in modules]

    def parsed_requires(self):
        return [r.split("::", 1) if "::" in r else (None, r) for r in self.requires]


class CppInfo:

    def __init__(self, set_defaults=False):
        self.components = defaultdict(lambda: _Component(set_defaults))
        self._package = _Component(set_defaults)

    def __getattr__(self, attr):
        # all cpp_info.xxx of not defined things will go to the global package
        return getattr(self._package, attr)

    def __setattr__(self, attr, value):
        if attr in ("components", "_package", "_aggregated"):
            super(CppInfo, self).__setattr__(attr, value)
        else:
            setattr(self._package, attr, value)

    def serialize(self):
        ret = {"root": self._package.serialize()}
        for component_name, info in self.components.items():
            ret[component_name] = info.serialize()
        return ret

    def deserialize(self, content):
        self._package = _Component.deserialize(content.pop("root"))
        for component_name, info in content.items():
            self.components[component_name] = _Component.deserialize(info)
        return self

    def save(self, path):
        save(path, json.dumps(self.serialize()))

    def load(self, path):
        content = json.loads(load(path))
        return self.deserialize(content)

    @property
    def has_components(self):
        return len(self.components) > 0

    def merge(self, other, overwrite=False):
        """Merge 'other' into self. 'other' can be an old cpp_info object
        Used to merge Layout source + build cpp objects info (editables)
        @type other: CppInfo
        @param other: The other CppInfo to merge
        @param overwrite: New values from other overwrite the existing ones
        """
        # Global merge
        self._package.merge(other._package, overwrite)
        # sysroot only of package, not components, first defined wins
        self._package.sysroot = self._package.sysroot or other._package.sysroot
        # COMPONENTS
        for cname, c in other.components.items():
            # Make sure each component created on the fly does not bring new defaults
            self.components.setdefault(cname, _Component(set_defaults=False)).merge(c, overwrite)

    def set_relative_base_folder(self, folder):
        """Prepend the folder to all the directories definitions, that are relative"""
        self._package.set_relative_base_folder(folder)
        for component in self.components.values():
            component.set_relative_base_folder(folder)

    def deploy_base_folder(self, package_folder, deploy_folder):
        """Prepend the folder to all the directories"""
        self._package.deploy_base_folder(package_folder, deploy_folder)
        for component in self.components.values():
            component.deploy_base_folder(package_folder, deploy_folder)

    def get_sorted_components(self):
        """
        Order the components taking into account if they depend on another component in the
        same package (not scoped with ::). First less dependant.

        :return: ``OrderedDict`` {component_name: component}
        """
        result = OrderedDict()
        opened = self.components.copy()
        while opened:
            new_open = OrderedDict()
            for name, c in opened.items():
                if not any(n in opened for n in c.required_component_names):
                    result[name] = c
                else:
                    new_open[name] = c
            if len(opened) == len(new_open):
                msg = ["There is a dependency loop in 'self.cpp_info.components' requires:"]
                for name, c in opened.items():
                    loop_reqs = ", ".join(n for n in c.required_component_names if n in opened)
                    msg.append(f"   {name} requires {loop_reqs}")
                raise ConanException("\n".join(msg))
            opened = new_open
        return result

    def aggregated_components(self):
        """Aggregates all the components as global values, returning a new CppInfo
        Used by many generators to obtain a unified, aggregated view of all components
        """
        # This method had caching before, but after a ``--deployer``, the package changes
        # location, and this caching was invalid, still pointing to the Conan cache instead of
        # the deployed
        if self.has_components:
            result = _Component()
            # Reversed to make more dependant first
            for component in reversed(self.get_sorted_components().values()):
                result.merge(component)
            # NOTE: The properties are not aggregated because they might refer only to the
            # component like "cmake_target_name" describing the target name FOR THE component
            # not the namespace.
            # FIXME: What to do about sysroot?
            result._properties = copy.copy(self._package._properties)
        else:
            result = copy.copy(self._package)
        aggregated = CppInfo()
        aggregated._package = result
        return aggregated

    def check_component_requires(self, conanfile):
        """ quality check for component requires, called by BinaryInstaller after package_info()
        - Check that all recipe ``requires`` are used if consumer recipe explicit opt-in to use
          component requires
        - Check that component external dep::comp dependency "dep" is a recipe "requires"
        - Check that every internal component require actually exist
        It doesn't check that external components do exist
        """
        if not self.has_components and not self._package.requires:
            return
        # Accumulate all external requires
        comps = self.required_components
        missing_internal = [c[1] for c in comps if c[0] is None and c[1] not in self.components]
        if missing_internal:
            raise ConanException(f"{conanfile}: Internal components not found: {missing_internal}")
        external = [c[0] for c in comps if c[0] is not None]
        if not external:
            return
        # Only direct host (not test) dependencies can define required components
        direct_dependencies = [d.ref.name for d in conanfile.requires.values()
                               if not d.build and not d.is_test and d.visible and not d.override]

        for e in external:
            if e not in direct_dependencies:
                raise ConanException(
                    f"{conanfile}: required component package '{e}::' not in dependencies")
        # TODO: discuss if there are cases that something is required but not transitive
        for e in direct_dependencies:
            if e not in external:
                raise ConanException(
                    f"{conanfile}: Required package '{e}' not in component 'requires'")

    @property
    def required_components(self):
        """Returns a list of tuples with (require, component_name) required by the package
        If the require is internal (to another component), the require will be None"""
        # FIXME: Cache the value
        # First aggregate without repetition, respecting the order
        ret = [r for r in self._package.requires]
        for comp in self.components.values():
            for r in comp.requires:
                if r not in ret:
                    ret.append(r)
        # Then split the names
        ret = [r.split("::") if "::" in r else (None, r) for r in ret]
        return ret
