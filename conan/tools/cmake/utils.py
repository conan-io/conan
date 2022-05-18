from conan.tools.cmake.cmakedeps import FIND_MODE_MODULE


def is_multi_configuration(generator):
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator or "Multi-Config" in generator


def get_file_name(conanfile, forced_module_mode=None):
    """Get the name of the file for the find_package(XXX)"""
    # This is used by the CMakeToolchain to adjust the XXX_DIR variables and the CMakeDeps. Both
    # to know the file name that will have the XXX-config.cmake files.
    if forced_module_mode or get_find_mode(conanfile) == FIND_MODE_MODULE:
        ret = conanfile.cpp_info.get_property("cmake_module_file_name")
        if ret:
            return ret
    ret = conanfile.cpp_info.get_property("cmake_file_name")
    return ret or conanfile.ref.name


def get_find_mode(conanfile):
    """
    :param conanfile: conanfile of the requirement
    :return: "none" or "config" or "module" or "both" or "config" when not set
    """
    tmp = conanfile.cpp_info.get_property("cmake_find_mode")
    if tmp is None:
        return "config"
    return tmp.lower()
