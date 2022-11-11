
def stdcpp_library(conanfile):
    """ Returns the name of the C++ standard library that can be passed
    to the linker, based on the current settings. Returs None if the name 
    of the C++ standard library file is not known.
    """
    libcxx = conanfile.settings.get_safe("compiler.libcxx")
    if libcxx in ["libstdc++", "libstdc++11"]:
        return "stdc++"
    elif libcxx in ["libc++"]:
        return "c++"
    elif libcxx in ["c++_shared"]:
        return "c++_shared"
    elif libcxx in ["c++_static"]:
        return "c++_static"
    return None
