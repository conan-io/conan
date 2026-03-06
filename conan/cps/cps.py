import json
import os
from enum import Enum

from conan.internal.model.cpp_info import CppInfo
from conan.internal.util.files import save, load


class CPSComponentType(Enum):
    DYLIB = "dylib"
    ARCHIVE = "archive"
    INTERFACE = "interface"
    EXE = "executable"
    JAR = "jar"
    UNKNOWN = "unknown"

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
        return CPSComponentType(_package_type_map.get(str(pkg_type), "unknown"))


class CPSComponent:
    def __init__(self, component_type=None):
        self.includes = []
        self.type = component_type or "unknown"
        self.definitions = {}
        self.requires = []
        self.link_requires = []
        self.location = None
        self.link_location = None
        self.link_languages = []
        self.link_libraries = []  # system libraries

    def serialize(self):
        component = {"type": str(self.type)}
        if self.requires:
            component["requires"] = self.requires
        if self.link_requires:
            component["link_requires"] = self.link_requires
        if self.includes:
            component["includes"] = [x.replace("\\", "/") for x in self.includes]
        if self.definitions:
            component["definitions"] = self.definitions
        if self.location:  # TODO: @prefix@
            component["location"] = self.location
        if self.link_location:
            component["link_location"] = self.link_location
        if self.link_libraries:
            component["link_libraries"] = self.link_libraries
        if self.link_languages:
            component["link_languages"] = self.link_languages
        return component

    @staticmethod
    def deserialize(data):
        comp = CPSComponent()
        comp.type = CPSComponentType(data.get("type"))
        comp.requires = data.get("requires", [])
        comp.link_requires = data.get("link_requires", [])
        comp.includes = data.get("includes", [])
        comp.definitions = data.get("definitions", {})
        comp.location = data.get("location")
        comp.link_location = data.get("link_location")
        comp.link_libraries = data.get("link_libraries", [])
        comp.link_languages = data.get("link_languages", [])
        return comp

    @staticmethod
    def from_cpp_info(cpp_info, conanfile, libname=None):
        cps_langs_mapping = {"C": "c", "C++": "cpp"}
        comp_langs = cpp_info.languages or conanfile.languages or []
        def definitions_from_conan(defines):
            result = {}
            for define in defines:
                if "=" in define:
                    k, v = define.split("=", 1)
                    result[k] = v
                else:
                    result[define] = None
            return result

        cps_comp = CPSComponent()
        if not libname:
            cps_comp.definitions = {
                cps_langs_mapping.get(lang, "*"): definitions_from_conan(cpp_info.defines)
                for lang in (comp_langs or ["*"])
            } if cpp_info.defines else {}
            cps_comp.includes = [x.replace("\\", "/") for x in cpp_info.includedirs]

        if not cpp_info.libs:
            cps_comp.type = CPSComponentType.INTERFACE
            return cps_comp

        if len(cpp_info.libs) > 1 and not libname:  # Multi-lib pkg without components defined
            cps_comp.type = CPSComponentType.INTERFACE
            return cps_comp

        cpp_info.deduce_locations(conanfile)
        cps_comp.type = CPSComponentType.from_conan(cpp_info.type)
        cps_comp.location = cpp_info.location
        cps_comp.link_location = cpp_info.link_location
        cps_comp.link_libraries = cpp_info.system_libs
        cps_comp.link_languages = [cps_langs_mapping[lang] for lang in comp_langs]
        required = cpp_info.requires
        cps_comp.requires = [f":{c}" if "::" not in c else c.replace("::", ":") for c in required]

        cps_comp.definitions = {
            cps_langs_mapping.get(lang, "*"): definitions_from_conan(cpp_info.defines)
            for lang in (comp_langs or ["*"])
        } if cpp_info.defines else {}
        return cps_comp

    def update(self, conf, conf_def):
        # TODO: conf not used at the moent
        self.link_languages = self.link_languages or conf_def.get("link_languages")
        self.location = self.location or conf_def.get("location")
        self.link_location = self.link_location or conf_def.get("link_location")
        self.link_libraries = self.link_libraries or conf_def.get("link_libraries")


class CPS:
    """ represents the CPS file for 1 package
    """
    def __init__(self, name=None, version=None):
        self.name = name
        self.version = version
        self.default_components = []
        self.components = {}
        self.configurations = []
        self.requires = []
        # Supplemental
        self.description = None
        self.license = None
        self.website = None
        self.prefix = None

    def serialize(self):
        cps = {"cps_version": "0.13.0",
               "name": self.name,
               "version": self.version}

        if self.prefix is not None:
            cps["prefix"] = self.prefix

        # Supplemental
        for data in "license", "description", "website":
            if getattr(self, data, None):
                cps[data] = getattr(self, data)

        if self.requires:
            cps["requires"] = self.requires

        if self.configurations:
            cps["configurations"] = self.configurations

        cps["default_components"] = self.default_components
        cps["components"] = {}
        for name, comp in self.components.items():
            cps["components"][name] = comp.serialize()

        return cps

    @staticmethod
    def deserialize(data):
        cps = CPS()
        cps.name = data.get("name")
        cps.prefix = data.get("prefix")
        cps.version = data.get("version")
        cps.license = data.get("license")
        cps.description = data.get("description")
        cps.website = data.get("website")
        cps.requires = data.get("requires")
        cps.configurations = data.get("configurations")
        cps.default_components = data.get("default_components")
        cps.components = {k: CPSComponent.deserialize(v)
                          for k, v in data.get("components", {}).items()}
        return cps

    @staticmethod
    def from_conan(dep):
        cps = CPS(dep.ref.name, str(dep.ref.version))
        cps.prefix = dep.package_folder.replace("\\", "/")
        # supplemental
        cps.license = dep.license
        cps.description = dep.description
        cps.website = dep.homepage

        cps.requires = {d.ref.name: None for d in dep.dependencies.host.values()}
        if dep.settings.get_safe("build_type"):
            cps.configurations = [str(dep.settings.build_type).lower()]

        if not dep.cpp_info.has_components:
            if dep.cpp_info.libs and len(dep.cpp_info.libs) > 1:
                comp = CPSComponent.from_cpp_info(dep.cpp_info, dep)  # base
                base_name = f"_{cps.name}"
                cps.components[base_name] = comp
                for lib in dep.cpp_info.libs:
                    comp = CPSComponent.from_cpp_info(dep.cpp_info, dep, lib)
                    comp.requires.insert(0, f":{base_name}")  # dep to the common one
                    cps.components[lib] = comp
                cps.default_components = dep.cpp_info.libs
                # FIXME: What if one lib is named equal to the package?
            else:
                # single component, called same as library
                component = CPSComponent.from_cpp_info(dep.cpp_info, dep)
                if not component.requires and dep.dependencies:
                    for transitive_dep in dep.dependencies.host.items():
                        dep_name = transitive_dep[0].ref.name
                        component.requires.append(f"{dep_name}:{dep_name}")

                # the component will be just the package name
                cps.default_components = [f"{dep.ref.name}"]
                cps.components[f"{dep.ref.name}"] = component
        else:
            sorted_comps = dep.cpp_info.get_sorted_components()
            for comp_name, comp in sorted_comps.items():
                component = CPSComponent.from_cpp_info(comp, dep)
                cps.components[comp_name] = component
            # Now by default all are default_components
            cps.default_components = [comp_name for comp_name in sorted_comps]

        return cps

    def to_conan(self):
        def strip_prefix(dirs):
            return [d.replace("@prefix@/", "") for d in dirs]

        def lib_location(loc, info):
            loc = loc.replace("@prefix@/", "")
            info.libdirs = [os.path.dirname(loc)]
            filename = os.path.basename(loc)
            basefile, ext = os.path.splitext(filename)
            if basefile.startswith("lib") and ext != ".lib":
                basefile = basefile[3:]
            info.libs = [basefile]

        def definitions(defs):
            # TODO: C/CPP specific as per CPS spec
            # "*" has less priority than specific language
            aggregated = {}
            aggregated.update(defs.get("*", {}))
            aggregated.update(defs.get("c", {}))
            aggregated.update(defs.get("cpp", {}))
            result = list(f"{k}={v}" if v is not None else k for k, v in aggregated.items())
            return result

        cpp_info = CppInfo()
        cpp_info.default_components = self.default_components
        for comp_name, comp in self.components.items():
            cpp_comp = cpp_info if len(self.components) == 1 else cpp_info.components[comp_name]
            cpp_comp.includedirs = strip_prefix(comp.includes)
            cpp_comp.defines = definitions(comp.definitions)
            cpp_info.set_property("cmake_file_name", self.name)
            cpp_info.set_property("cmake_target_name", f"{self.name}::{comp_name}")
            if comp.link_location:
                link_location = comp.link_location
                lib_location(link_location, cpp_comp)
                location = comp.location
                location = location.replace("@prefix@/", "")
                cpp_comp.bindirs = [os.path.dirname(location)]
            elif comp.location:
                location = comp.location
                lib_location(location, cpp_comp)
            requires = comp.link_requires + comp.requires
            for r in requires:
                cpp_comp.requires.append(r[1:] if r.startswith(":") else r.replace(":", "::"))
            cpp_comp.system_libs = comp.link_libraries

        return cpp_info

    def save(self, folder):
        filename = os.path.join(folder, f"{self.name}.cps")
        save(filename, json.dumps(self.serialize(), indent=2))
        return filename

    @staticmethod
    def load(file):
        contents = load(file)
        base = CPS.deserialize(json.loads(contents))

        path, name = os.path.split(file)
        basename, ext = os.path.splitext(name)
        # Find, load and merge configuration specific files
        for conf in "release", "debug":
            full_conf = os.path.join(path, f"{basename}@{conf}{ext}")
            if os.path.exists(full_conf):
                conf_content = json.loads(load(full_conf))
                for comp, comp_def in conf_content.get("components", {}).items():
                    existing = base.components.get(comp)
                    if existing:
                        existing.update(conf, comp_def)
                    else:
                        base.components[comp] = comp_def
        return base
