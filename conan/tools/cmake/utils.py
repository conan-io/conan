def is_multi_configuration(generator):
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator or "Multi-Config" in generator


def get_file_name(conanfile):
    """Get the name of the file for the find_package(XXX)"""
    # This is used by the CMakeToolchain to adjust the XXX_DIR variables and the CMakeDeps. Both
    # to know the file name that will have the XXX-config.cmake files.
    ret = conanfile.new_cpp_info.get_property("cmake_file_name", "CMakeDeps")
    if not ret:
        ret = conanfile.cpp_info.get_filename("cmake_find_package_multi", default_name=False)
    return ret or conanfile.ref.name

