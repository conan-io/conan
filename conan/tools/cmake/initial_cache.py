import os

from conan.tools.cmake.presets import load_cmake_presets, get_configure_preset
from conans.util.files import save, load


class CMakeInitialCache:
    """CMakeToolchain sub-generator"""
    """
    # Build the vtkHybrid kit.
    set(VTK_USE_HYBRID ON CACHE BOOL "doc string")
    """

    def __init__(self, conanfile, cmaketoolchain):
        self._conanfile = conanfile

        cmake_presets = load_cmake_presets(conanfile.generators_folder)
        configure_preset = get_configure_preset(cmake_presets, conanfile)
        self._cache_variables = configure_preset["cacheVariables"]

    def _content(self):
        return {}

    def generate(self):
        cache_cmake_paath = os.path.join(self._conanfile.generators_folder, "CMakeInitialCache.cmake")
        if not os.path.exists(cache_cmake_paath):
            content = self._content()
            save(cache_cmake_paath, content)
