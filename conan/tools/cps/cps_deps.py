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

    def _component(self, package_type, cpp_info, build_type):
        component = {}
        component["Type"] = self._package_type_map.get(str(package_type), "unknown")
        component["Definitions"] = cpp_info.defines
        component["Includes"] = [x.replace("\\", "/") for x in cpp_info.includedirs]

        if not cpp_info.libs:  # No compiled libraries, header-only
            return component
        is_shared = package_type == "shared-library"
        if is_shared and self.conanfile.settings.os == "Windows":
            dll_location = self.find_library(cpp_info.libdirs, cpp_info.bindirs,
                                             cpp_info.libs, is_shared, dll=True)
            import_library = self.find_library(cpp_info.libdirs, cpp_info.bindirs,
                                               cpp_info.libs, is_shared, dll=False)
            locations = {'Location': dll_location,
                         'Link-Location': import_library}
            component["Configurations"] = {build_type: locations}  # noqa
        elif package_type == "static-library":
            library_location = self.find_library(cpp_info.libdirs, cpp_info.bindirs,
                                                 cpp_info.libs, is_shared, dll=False)
            component["Configurations"] = {build_type: {'Location': library_location}}

        return component

    def generate(self):
        self.conanfile.output.info(f"[CPSDeps] generators folder {self.conanfile.generators_folder}")
        deps = self.conanfile.dependencies.host.items()
        for _, dep in deps:
            self.conanfile.output.info(f"[CPSDeps]: dep {dep.ref.name}")

            cps = {"Cps-Version": "0.8.1",
                   "Name": dep.ref.name,
                   "Version": str(dep.ref.version)}

            build_type = str(self.conanfile.settings.build_type).lower()
            cps["Configurations"] = [build_type]

            if not dep.cpp_info.has_components:
                # single component, called same as library
                component = self._component(dep.package_type, dep.cpp_info, build_type)
                if dep.dependencies:
                    for transitive_dep in dep.dependencies.items():
                        dep_name = transitive_dep[0].ref.name
                        component["Requires"] = [f"{dep_name}:{dep_name}"]

                cps["Default-Components"] = [f"{dep.ref.name}"]
                cps["Components"] = {f"{dep.ref.name}": component}
            else:
                sorted_comps = dep.cpp_info.get_sorted_components()
                for comp_name, comp in sorted_comps.items():
                    component = self._component(dep.package_type, comp, build_type)
                    cps.setdefault("Components", {})[comp_name] = component
                cps["Default-Components"] = [comp_name for comp_name in sorted_comps]

            output_file = os.path.join(self.conanfile.generators_folder, f"{dep.ref.name}.cps")
            cps_json = json.dumps(cps, indent=4)
            save(self.conanfile, output_file, cps_json)
