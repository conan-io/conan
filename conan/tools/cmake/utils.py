def is_multi_configuration(generator):
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator or "Multi-Config" in generator


def get_file_name(conanfile, find_module_mode=False):
    """Get the name of the file for the find_package(XXX)"""
    # This is used by the CMakeToolchain to adjust the XXX_DIR variables and the CMakeDeps. Both
    # to know the file name that will have the XXX-config.cmake files.
    if find_module_mode:
        ret = conanfile.cpp_info.get_property("cmake_module_file_name")
        if ret:
            return ret
    ret = conanfile.cpp_info.get_property("cmake_file_name")
    return ret or conanfile.ref.name

