import os

from conan.tools.cmake.presets import load_cmake_presets, get_configure_preset
from conans.util.files import save, save_append


def _format_cache_variables(cache_variables):
    ret = []
    for name, value in cache_variables.items():
        if isinstance(value, bool):
            type_ = "BOOL"
            v = "ON" if value else "OFF"
        elif value in ("ON", "OFF"):
            type_ = "BOOL"
            v = value
        else:
            type_ = "STRING"
            v = f'"{value}"'
        ret.append(f'set({name} {v} CACHE {type_} "" FORCE)')
    return "\n".join(ret)


def get_initial_cache_path(conanfile):
    return os.path.join(conanfile.generators_folder, "CMakeInitialCache.cmake")


def save_cmake_initial_cache(conanfile):
    """
    Save a *.cmake build helper file to save all the CACHE variables (-DXXX vars) in one
    file instead of passing all of them via CLI.

    Note: it needs to load the cmake presets file to load all the existing cache variables
    already defined.

    :param conanfile: ``ConanFile`` instance
    """
    cmake_presets = load_cmake_presets(conanfile.generators_folder)
    configure_preset = get_configure_preset(cmake_presets, conanfile)
    toolchain_file = configure_preset.get("toolchainFile")
    cache_variables = configure_preset["cacheVariables"]

    generator_folder = conanfile.generators_folder
    variables = {}

    if toolchain_file:
        if os.path.isabs(toolchain_file):
            toolchain_file = toolchain_file
        else:
            toolchain_file = os.path.join(generator_folder, toolchain_file)
        variables["CMAKE_TOOLCHAIN_FILE"] = toolchain_file.replace("\\", "/")

    if conanfile.package_folder:
        pkg_folder = conanfile.package_folder.replace("\\", "/")
        variables["CMAKE_INSTALL_PREFIX"] = pkg_folder

    variables.update(cache_variables)

    cache_cmake_path = get_initial_cache_path(conanfile)
    content = _format_cache_variables(variables)
    save(cache_cmake_path, content)


def update_cmake_initial_cache(conanfile, cache_variables):
    """
    Update the existing `CMakeInitialCache.cmake` file with new cache variables

    :param conanfile: ``ConanFile`` instance
    :param cache_variables: ``dict`` with extra variables to be saved as CACHE ones
    """
    if not cache_variables:
        return
    cache_cmake_path = get_initial_cache_path(conanfile)
    content = _format_cache_variables(cache_variables)
    save_append(cache_cmake_path, content)
