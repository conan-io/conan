import os
from collections import OrderedDict

from conans.client.graph.compute_pid import run_validate_package_id
from conans.client.loader import load_python_file
from conans.errors import conanfile_exception_formatter
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
# TODO: Improve definition of cppstd for each compiler version
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

    versions = {"gcc": ["9", "10", "11", "12"],
                "msvc": ["190", "191", "192", "193"],
                "clang": ["12", "13", "14", "15"],
                "apple-clang": ["10.0", "11.0", "12.0", "13"]
                }
    valid_versions = versions.get(compiler)
    if valid_versions:
        possible_versions = reversed(valid_versions)
        factors.append([("compiler.version", v) for v in possible_versions])

    # This will be simplified if we know if the language is pure C
    cppstds = {"gcc": [None, "98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17",
                       "20", "gnu20", "23", "gnu23"],
               "msvc": ["98", "14", "17", "20", "23"],
               "clang": [None, "98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17",
                         "20", "gnu20", "23", "gnu23"],
               "apple-clang": [None, "98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17",
                               "20", "gnu20"]
               }
    # This can be improved reducing the cppstd to the compiler versions. A conan.tools helper?
    valid_cppstds = cppstds.get(compiler)
    if valid_cppstds:
       valid_cppstds = reversed(valid_cppstds)
       factors.append([("compiler.cppstd", v) for v in valid_cppstds])

    if compiler == "msvc":
        runtime = conanfile.settings.get_safe("compiler.runtime")
        if runtime is None:
            factors.append([("compiler.runtime", "dynamic")])
            factors.append([("compiler.runtime_type", build_type or "Release")])

    result = []
    combinations = list(product(*factors))
    for combination in combinations:
        result.append({"settings": combination})
    return result
"""


class BinaryCompatibility:
    def __init__(self, cache):
        compatible_folder = os.path.join(cache.plugins_path, "compatibility")
        compatible_file = os.path.join(compatible_folder, "compatibility.py")
        if not os.path.isfile(compatible_file):
            save(compatible_file, default_compat)
            save(os.path.join(compatible_folder, "app_compat.py"), default_app_compat)
        mod, _ = load_python_file(compatible_file)
        self._compatibility = mod.compatibility

    def compatibles(self, conanfile):
        compat_infos = []
        if hasattr(conanfile, "compatibility") and callable(conanfile.compatibility):
            with conanfile_exception_formatter(conanfile, "compatibility"):
                recipe_compatibles = conanfile.compatibility()
                compat_infos.extend(self._compatible_infos(conanfile, recipe_compatibles))

        plugin_compatibles = self._compatibility(conanfile)
        compat_infos.extend(self._compatible_infos(conanfile, plugin_compatibles))

        result = OrderedDict()
        for c in compat_infos:
            conanfile.info = c
            run_validate_package_id(conanfile)
            pid = c.package_id()
            if pid not in result and not c.invalid:
                result[pid] = c
        return result

    @staticmethod
    def _compatible_infos(conanfile, compatibles):
        result = []
        if compatibles:
            for elem in compatibles:
                compat_info = conanfile.original_info.clone()
                settings = elem.get("settings")
                if settings:
                    compat_info.settings.update_values(settings)
                options = elem.get("options")
                if options:
                    compat_info.options.update(options_values=OrderedDict(options))
                result.append(compat_info)
        return result
