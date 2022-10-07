
def stdcpp_library(conanfile):
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
