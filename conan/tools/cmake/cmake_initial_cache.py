import os

from conans.util.files import save, save_append, load


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
    return ret


def get_initial_cache_path(conanfile):
    return os.path.join(conanfile.generators_folder, "conan_initial_cache.cmake")


def save_cmake_initial_cache(conanfile, cache_variables):
    """
    Save a conan_initial_cache.cmake file to save all the CACHE variables (-DXXX vars) in one
    file instead of passing all of them via CLI.

    :param conanfile: ``ConanFile`` instance
    :param cache_variables: ``dict`` with variables to be saved as CACHE ones
    """
    cache_cmake_path = get_initial_cache_path(conanfile)
    content = _format_cache_variables(cache_variables)
    save(cache_cmake_path, "\n".join(content))


def update_cmake_initial_cache(conanfile, cache_variables):
    """
    Update the existing `conan_initial_cache.cmake` file with new cache variables

    :param conanfile: ``ConanFile`` instance
    :param cache_variables: ``dict`` with variables to be saved as CACHE ones
    """
    cache_cmake_path = get_initial_cache_path(conanfile)
    new_content = []
    original_content = load(cache_cmake_path)
    # Pruning duplicated lines. If the variable already exists but the value is different
    # then it'll override the original value
    for line in _format_cache_variables(cache_variables):
        if line not in original_content:
            new_content.append(line)
    save_append(cache_cmake_path, "\n".join(new_content))
