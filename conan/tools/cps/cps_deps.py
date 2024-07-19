from conan.cps.cps import CPS
from conan.tools.files import save

import glob
import json
import os


class CPSDeps:
    def __init__(self, conanfile):
        self.conanfile = conanfile

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
        mapping = {}
        for _, dep in deps:
            self.conanfile.output.info(f"[CPSDeps]: dep {dep.ref.name}")

            cps_in_package = os.path.join(dep.package_folder, f"{dep.ref.name}.cps")
            if os.path.exists(cps_in_package):
                mapping[dep.ref.name] = cps_in_package
                continue

            cps = CPS.from_conan(dep)
            output_file = cps.save(self.conanfile.generators_folder)
            mapping[dep.ref.name] = output_file

        name = ["cpsmap",
                self.conanfile.settings.get_safe("arch"),
                self.conanfile.settings.get_safe("build_type"),
                self.conanfile.options.get_safe("shared")]
        name = "-".join([f for f in name if f]) + ".json"
        self.conanfile.output.info(f"Generating CPS mapping file: {name}")
        save(self.conanfile, name, json.dumps(mapping, indent=2))
