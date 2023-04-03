import os


def is_multi_configuration(generator):
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator or "Multi-Config" in generator


def relativize_cmake_path(folder, conanfile):
    generators_folder = conanfile.generators_folder
    base_folder = conanfile.folders._base_generators
    if os.path.commonpath([folder, base_folder]) == base_folder:
        rel_path = os.path.relpath(folder, generators_folder)
        rel_path = rel_path.replace('\\', '/').replace('$', '\\$').replace('"', '\\"')
        root_folder = f"${{CMAKE_CURRENT_LIST_DIR}}/{rel_path}"
    else:
        root_folder = folder.replace('\\', '/').replace('$', '\\$').replace('"', '\\"')
    return root_folder
