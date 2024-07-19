import json
import os
from enum import Enum

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


class CPSComponent:
    def __init__(self, component_type=None):
        self.includes = []
        self.type = component_type or "unknown"
        self.definitions = []
        self.requires = []

    def serialize(self):
        component = {"type": self.type,
                     "includes": [x.replace("\\", "/") for x in self.includes]}
        if self.definitions:
            component["definitions"] = self.definitions
        return component

    def deserialize(self):
        pass

    @staticmethod
    def from_cpp_info(cpp_info):
        cps_comp = CPSComponent()
        cps_comp.type = CPSComponentType.from_conan(str(cpp_info.type))
        cps_comp.definitions = cpp_info.defines
        cps_comp.includes = [x.replace("\\", "/") for x in cpp_info.includedirs]
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
        if dep.settings.get_safe("build_type"):
            cps.configurations = [str(dep.settings.build_type).lower()]

        if not dep.cpp_info.has_components:
            # single component, called same as library
            component = CPSComponent.from_cpp_info(dep.cpp_info)
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
                component = CPSComponent.from_cpp_info(comp)
                cps.components[comp_name] = component
            # Now by default all are default_components
            cps.default_components = [comp_name for comp_name in sorted_comps]

        return cps

    def save(self, folder):
        filename = os.path.join(folder, f"{self.name}.cps")
        save(filename, json.dumps(self.serialize(), indent=4))
        return filename
