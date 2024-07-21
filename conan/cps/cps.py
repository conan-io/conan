import glob
import json
import os
from enum import Enum

from conan.api.output import ConanOutput
from conans.model.pkg_type import PackageType
from conans.util.files import save


class CPSComponentType(Enum):
    DYLIB = "dylib"
    ARCHIVE = "archive"
    INTERFACE = "interface"
    EXE = "exe"
    JAR = "jar"

    def __str__(self):
        return self.value

    def __eq__(self, other):
        # This is useful for comparing with string type at user code, like ``type == "xxx"``
        return super().__eq__(CPSComponentType(other))

    @staticmethod
    def from_conan(pkg_type):
        _package_type_map = {
            "shared-library": "dylib",
            "static-library": "archive",
            "header-library": "interface",
            "application": "executable"
        }
        return _package_type_map.get(str(pkg_type), "unknown")


def deduce_full_lib_info(libname, full_lib, cpp_info, pkg_type):
    if full_lib.get("type") is not None:
        assert "location" in full_lib, f"If 'type' is specified in library {libname}, 'location' too"
        return

    # Recipe didn't specify things, need to auto deduce
    libdirs = [x.replace("\\", "/") for x in cpp_info.libdirs]
    bindirs = [x.replace("\\", "/") for x in cpp_info.bindirs]

    static_patterns = [f"{libname}.lib", f"{libname}.a"]
    shared_patterns = [f"lib{libname}.so", f"lib{libname}.so.*", f"lib{libname}.dylib",
                       f"lib{libname}.*dylib"]
    dll_patterns = [f"{libname}.dll"]

    def _find_matching(patterns, dirs):
        matches = set()
        for pattern in patterns:
            for d in dirs:
                matches.update(glob.glob(f"{d}/{pattern}"))
        matches = [m for m in matches if not os.path.islink(m)]
        if len(matches) == 1:
            return next(iter(matches))

    static_location = _find_matching(static_patterns, libdirs)
    shared_location = _find_matching(shared_patterns, libdirs)
    dll_location = _find_matching(dll_patterns, bindirs)
    if static_location:
        if shared_location:
            ConanOutput().warning(f"Lib {libname} has both static {static_location} and "
                                  f"shared {shared_location} in the same package")
            if pkg_type is PackageType.STATIC:
                full_lib["location"] = static_location
                full_lib["type"] = PackageType.STATIC
            else:
                full_lib["location"] = shared_location
                full_lib["type"] = PackageType.SHARED
        elif dll_location:
            full_lib["location"] = dll_location
            full_lib["link_location"] = static_location
            full_lib["type"] = PackageType.SHARED
        else:
            full_lib["location"] = static_location
            full_lib["type"] = PackageType.STATIC
    elif shared_location:
        full_lib["location"] = shared_location
        full_lib["type"] = PackageType.SHARED
    elif dll_location:
        # Only .dll but no link library
        full_lib["location"] = dll_location
        full_lib["type"] = PackageType.SHARED
    if full_lib["type"] != pkg_type:
        ConanOutput().warning(f"Lib {libname} deduced as '{full_lib['type']}, "
                              f"but 'package_type={pkg_type}'")


class CPSComponent:
    def __init__(self, component_type=None):
        self.includes = []
        self.type = component_type or "unknown"
        self.definitions = []
        self.requires = []
        self.location = None
        self.link_location = None

    def serialize(self):
        component = {"type": self.type,
                     "includes": [x.replace("\\", "/") for x in self.includes]}
        if self.definitions:
            component["definitions"] = self.definitions
        if self.location:  # TODO: @prefix@
            component["location"] = self.location
        if self.link_location:
            component["link_location"] = self.link_location
        return component

    def deserialize(self):
        pass

    @staticmethod
    def from_cpp_info(cpp_info, pkg_type, libname=None):
        cps_comp = CPSComponent()
        if not libname:
            cps_comp.definitions = cpp_info.defines
            # TODO: @prefix@
            cps_comp.includes = [x.replace("\\", "/") for x in cpp_info.includedirs]

        if not cpp_info.libs:
            return cps_comp

        if len(cpp_info.libs) > 1 and not libname:  # Multi-lib pkg without components defined
            return cps_comp

        libname = libname or cpp_info.libs[0]
        full_lib = cpp_info.full_libs[libname]
        deduce_full_lib_info(libname, full_lib, cpp_info, pkg_type)
        cps_comp.type = CPSComponentType.from_conan(full_lib.get("type"))
        cps_comp.location = full_lib.get("location")
        cps_comp.link_location = full_lib.get("link_location")
        return cps_comp


class CPS:
    """ represents the CPS file for 1 package
    """
    def __init__(self, name=None, version=None):
        self.name = name
        self.version = version
        self.default_components = []
        self.components = {}
        self.configurations = []
        # Supplemental
        self.description = None
        self.license = None
        self.website = None

    def serialize(self):
        cps = {"cps_version": "0.12.0",
               "name": self.name,
               "version": self.version,
               "default_components": self.default_components,
               "components": {}}

        # Supplemental
        for data in "license", "description", "website":
            if getattr(self, data, None):
                cps[data] = getattr(self, data)

        if self.configurations:
            cps["configurations"] = self.configurations

        for name, comp in self.components.items():
            cps["components"][name] = comp.serialize()

        return cps

    def deserialize(self):
        pass

    @staticmethod
    def from_conan(dep):
        cps = CPS(dep.ref.name, str(dep.ref.version))
        # supplemental
        cps.license = dep.license
        cps.description = dep.description
        cps.website = dep.homepage
        if dep.settings.get_safe("build_type"):
            cps.configurations = [str(dep.settings.build_type).lower()]

        if not dep.cpp_info.has_components:
            if dep.cpp_info.libs and len(dep.cpp_info.libs) > 1:
                comp = CPSComponent.from_cpp_info(dep.cpp_info, dep.package_type)  # base
                base_name = cps.name
                cps.components[base_name] = comp
                for lib in dep.cpp_info.libs:
                    comp = CPSComponent.from_cpp_info(dep.cpp_info, dep.package_type, lib)
                    comp.requires.insert(0, base_name)  # dep to the common one
                    cps.components[lib] = comp
                cps.default_components = [dep.cpp_info.libs]
                # FIXME: What if one lib is named equal to the package?
            else:
                # single component, called same as library
                component = CPSComponent.from_cpp_info(dep.cpp_info, dep.package_type)
                # self._component(dep.package_type, dep.cpp_info, build_type)
                if dep.dependencies:
                    for transitive_dep in dep.dependencies.items():
                        dep_name = transitive_dep[0].ref.name
                        component.requires = [f"{dep_name}:{dep_name}"]

                # the component will be just the package name
                cps.default_components = [f"{dep.ref.name}"]
                cps.components[f"{dep.ref.name}"] = component
        else:
            sorted_comps = dep.cpp_info.get_sorted_components()
            for comp_name, comp in sorted_comps.items():
                component = CPSComponent.from_cpp_info(comp, dep.package_type)
                cps.components[comp_name] = component
            # Now by default all are default_components
            cps.default_components = [comp_name for comp_name in sorted_comps]

        return cps

    def save(self, folder):
        filename = os.path.join(folder, f"{self.name}.cps")
        save(filename, json.dumps(self.serialize(), indent=4))
        return filename
