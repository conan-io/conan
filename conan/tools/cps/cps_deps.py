from conan.tools.apple import is_apple_os
from conan.tools.files import save

import glob
import json
import os


class CPSDeps:
    def __init__(self, conanfile):
        self.conanfile = conanfile

    _package_type_map = {
        "shared-library": "dylib",
        "static-library": "archive",
        "header-library": "interface"
    }

    def find_library(self, libdirs, bindirs, name, shared, dll):
        libdirs = [x.replace("\\", "/") for x in libdirs]
        bindirs = [x.replace("\\", "/") for x in bindirs]
        libname = name[0]  # assume one library per component
        if shared and not dll:
            patterns = [f"lib{libname}.so", f"lib{libname}.so.*", f"lib{libname}.dylib",
                        f"lib{libname}.*dylib", f"{libname}.lib"]
        elif shared and dll:
            patterns = [f"{libname}.dll"]
        else:
            patterns = [f"lib{libname}.a", f"{libname}.lib"]

        matches = set()
        search_dirs = bindirs if self.conanfile.settings.os == "Windows" and shared and dll else libdirs
        for folder in search_dirs:
            for pattern in patterns:
                glob_expr = f"{folder}/{pattern}"
                matches.update(glob.glob(glob_expr))

        if len(matches) == 1:
            return next(iter(matches))
        elif len(matches) >= 1:
            # assume at least one is not a symlink
            return [x for x in list(matches) if not os.path.islink(x)][0]
        else:
            self.conanfile.output.error(f"[CPSDeps] Could not locate library: {libname}")
            return None

    def generate(self):
        self.conanfile.output.info(f"[CPSDeps] generators folder {self.conanfile.generators_folder}")
        deps = self.conanfile.dependencies.host.items()
        for _, dep in deps:
            self.conanfile.output.info(f"[CPSDeps]: dep {dep.ref.name}")

            cps = {"Cps-Version": "0.8.1",
                   "Name": dep.ref.name,
                   "Version": str(dep.ref.version)}
            """
                   "Platform": {
                       "Isa": "arm64" if self.conanfile.settings.arch == "armv8" else self.conanfile.settings.arch,
                       "Kernel": "darwin" if is_apple_os(self.conanfile) else str(
                           self.conanfile.settings.os).lower()
                   }}
            """
            build_type = str(self.conanfile.settings.build_type).lower()
            cps["Configurations"] = [build_type]

            if not dep.cpp_info.has_components:
                # single component, called same as library
                component = {}
                component["Type"] = self._package_type_map.get(str(dep.package_type), "unknown")
                component["Definitions"] = dep.cpp_info.defines
                component["Includes"] = [x.replace("\\", "/") for x in dep.cpp_info.includedirs]

                """is_shared = dep.package_type == "shared-library"
                if is_shared and self.conanfile.settings.os == "Windows":
                    dll_location = self.find_library(dep.cpp_info.libdirs, dep.cpp_info.bindirs,
                                                     dep.cpp_info.libs, is_shared, dll=True)
                    import_library = self.find_library(dep.cpp_info.libdirs, dep.cpp_info.bindirs,
                                                       dep.cpp_info.libs, is_shared, dll=False)
                    component["Configurations"] = {
                        build_type: {'Location': dll_location, 'Link-Location': import_library}}
                else:
                    library_location = self.find_library(dep.cpp_info.libdirs, dep.cpp_info.bindirs,
                                                         dep.cpp_info.libs, is_shared, dll=False)
                    component["Configurations"] = {build_type: {'Location': library_location}}

                if dep.dependencies:
                    for transitive_dep in dep.dependencies.items():
                        self.conanfile.output.info(
                            f"[CPSGEN] {dep} has a dependency on: {transitive_dep[0].ref}")
                        dep_name = transitive_dep[0].ref.name
                        component["Requires"] = [f"{dep_name}:{dep_name}"]
"""
                cps["Default-Components"] = [f"{dep.ref.name}"]
                cps["Components"] = {f"{dep.ref.name}": component}

            output_file = os.path.join(self.conanfile.generators_folder, f"{dep.ref.name}.cps")
            cps_json = json.dumps(cps, indent=4)
            save(self.conanfile, output_file, cps_json)
