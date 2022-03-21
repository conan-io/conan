import os

from conans.client.loader import load_python_file
from conans.util.files import save


# TODO: Define other compatibility besides applications
default_compat = """
from app_compat import app_compat
def compatibility(conanfile):
    if conanfile.package_type == "application":
        return app_compat(conanfile)

    # TODO: Define compat for libraries and other stuff
"""

# TODO: missing runtime, libcxx, cppstd, etc
# TODO: Improve conanfile.settings.get_item("compiler", compiler).version.values_range
default_app_compat = """
from itertools import product
def app_compat(conanfile):
    # os, and arch should be at least defined, if not, not try
    os_ = conanfile.settings.get_safe("os")
    arch = conanfile.settings.get_safe("arch")
    if os_ is None or arch is None:
        return

    factors = []
    build_type = conanfile.settings.get_safe("build_type")
    if build_type is None:
        factors.append([("build_type", "Release")])

    compiler = conanfile.settings.get_safe("compiler")
    if compiler is None:
        compilers = {"Windows": "msvc",
                     "Macos": "apple-clang"}
        compiler = compilers.get(os_, "gcc")
        factors.append([("compiler", compiler)])

    # This will be simplified if we know if the language is pure C
    cppstd = conanfile.settings.get_safe("compiler.cppstd")
    if not cppstd:
        for cppstd in ["11", "14", "17", "20"]:
            pass

    version = conanfile.settings.get_safe("compiler.version")
    if version is None:
        possible_versions = conanfile.settings.get_item("compiler", compiler).version.values_range
        possible_versions = reversed(possible_versions)
        factors.append([("compiler.version", v) for v in possible_versions])

    print("FACTORS", factors)
    result = []
    combinations = list(product(*factors))
    print("COMBINATIONS", combinations)
    for combination in combinations:
        result.append({"settings": combination})
    return result
"""


class BinaryCompatibilityPlugin:
    def __init__(self, cache):
        compatible_folder = os.path.join(cache.plugins_path, "compatibility")
        compatible_file = os.path.join(compatible_folder, "compatibility.py")
        if not os.path.isfile(compatible_file):
            save(compatible_file, default_compat)
            save(os.path.join(compatible_folder, "app_compat.py"), default_app_compat)
        mod, _ = load_python_file(compatible_file)
        self._compatibility = mod.compatibility

    def compatibles(self, conanfile):
        if self._compatibility is None:
            return  # We might want to define a common compatibility for cppstd, for example

        cache_compatibles = []
        list_of_compatibles = self._compatibility(conanfile) or []
        for elem in list_of_compatibles:
            compat = conanfile.original_info.clone()
            settings = elem.get("settings")
            if settings:
                # This update only modifies existing binaries, but it will not add unexisting
                compat.settings.update_values(settings)
            cache_compatibles.append(compat)
        return cache_compatibles
