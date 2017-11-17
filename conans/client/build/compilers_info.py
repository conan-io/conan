
architecture_dict = {"x86_64": "-m64", "x86": "-m32"}


def stdlib_flags(compiler, libcxx):
    ret = []
    if compiler and "clang" in compiler:
        if libcxx == "libc++":
            ret.append("-stdlib=libc++")
        else:
            ret.append("-stdlib=libstdc++")
    elif compiler == "sun-cc":
        flag = _sun_cc_libcxx_flags_dict.get(libcxx, None)
        if flag:
            ret.append(flag)
    return ret


def stdlib_defines(compiler, libcxx):
    ret = []
    # Maybe clang is using the standard library from g++
    if compiler == "gcc" or compiler == "clang":
        if libcxx == "libstdc++":
            ret.append("_GLIBCXX_USE_CXX11_ABI=0")
        elif str(libcxx) == "libstdc++11":
            ret.append("_GLIBCXX_USE_CXX11_ABI=1")
    return ret


def cppstd_flag(compiler, compiler_version, cppstd):
    if not compiler or not compiler_version or not cppstd:
        return ""
    func = {"gcc": _cppstd_gcc,
            "clang": _cppstd_clang,
            "apple-clang": _cppstd_apple_clang,
            "Visual Studio": _cppstd_visualstudio}.get(compiler, None)
    flag = None
    if func:
        flag = func(compiler_version, cppstd)
    return flag


def cstd_flag(compiler, compiler_version, cstd):
    if not compiler or not compiler_version or not cstd:
        return ""
    func = {"gcc": _cstd_gcc,
            "clang": _cstd_clang,
            "apple-clang": _cstd_apple_clang,
            "Visual Studio": _cstd_visual_studio}.get(compiler, None)
    flag = None
    if func:
        flag = func(compiler_version, cstd)
    return flag


def cppstd_default(compiler, compiler_version):

    default = {"gcc": _gcc_cppstd_default(compiler_version),
               "clang": "98",
               "apple-clang": "98"}.get(compiler, None)
    return default


def cstd_default(compiler, compiler_version):

    default = {"gcc": _gcc_cstd_default(compiler, compiler_version),
               "clang": "11gnu",
               "apple-clang": "11gnu"}.get(compiler, None)
    return default


def _gcc_cppstd_default(compiler_version):
    if int(float(compiler_version)) <= 5:
        return "98gnu"
    if int(float(compiler_version)) <= 7:
        return "14gnu"
    return None


def _gcc_cstd_default(compiler_version):
    if int(float(compiler_version)) <= 4:
        return "90gnu"
    return "11gnu"


def _cstd_visual_studio(_, __):
    return None


def _cppstd_visualstudio(visual_version, cppstd):

    v14 = None
    v17 = None

    if int(visual_version) >= 14:
        v14 = "c++14"
        v17 = "c++latest"
    if int(visual_version) >= 15:
        v17 = "c++17"

    flag = {"14": v14, "17": v17}.get(cppstd, None)
    return "/std=%s" % flag if flag else None


def _cstd_apple_clang(clang_version, cstd):
    """https://github.com/Kitware/CMake/blob/1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/
    Modules/Compiler/GNU-CXX.cmake"""
    v90 = v90gnu = v99 = v99gnu = v11 = v11gnu = None

    if not float(clang_version) < 4.0:
        v90 = "c90"
        v90gnu = "gnu90"
        v99 = "c99"
        v99gnu = "gnu99"
        v11 = "c1x"
        v11gnu = "gnu1x"

    flag = {"90": v90, "90gnu": v90gnu,
            "99": v99, "99gnu": v99gnu,
            "11": v11, "11gnu": v11gnu}.get(cstd, None)

    return "-std=%s" % flag if flag else None


def _cppstd_apple_clang(clang_version, cppstd):
    """
    Inspired in:
    https://github.com/Kitware/CMake/blob/1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/
    Modules/Compiler/AppleClang-CXX.cmake
    """

    v98 = v98gnu = v11 = v11gnu = v14 = v14gnu = v17 = v17gnu = None

    if not float(clang_version) < 4.0:
        v98 = "98"
        v98gnu = "98gnu"
        v11 = "c++11"
        v11gnu = "gnu++11"

    if not float(clang_version) < 6.1:
        v14 = "c++14"
        v14gnu = "gnu++14"
    elif not float(clang_version) < 5.1:
        v14 = "c++1y"
        v14gnu = "gnu++1y"

    if not float(clang_version) < 6.1:
        v17 = "c++1z"
        v17gnu = "gnu++1z"

    flag = {"98": v98, "98gnu": v98gnu,
            "11": v11, "11gnu": v11gnu,
            "14": v14, "14gnu": v14gnu,
            "17": v17, "17gnu": v17gnu}.get(cppstd, None)

    return "-std=%s" % flag if flag else None


def _cstd_clang(clang_version, cstd):
    """https://github.com/Kitware/CMake/blob/1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/
    Modules/Compiler/GNU-CXX.cmake"""
    v90 = v90gnu = v99 = v99gnu = v11 = v11gnu = None

    if not float(clang_version) < 3.4:
        v90 = "c90"
        v90gnu = "gnu90"
        v99 = "c99"
        v99gnu = "gnu99"
        v11 = "c1x"
        v11gnu = "gnu1x"

    flag = {"90": v90, "90gnu": v90gnu,
            "99": v99, "99gnu": v99gnu,
            "11": v11, "11gnu": v11gnu}.get(cstd, None)

    return "-std=%s" % flag if flag else None


def _cppstd_clang(clang_version, cppstd):
    """
    Inspired in:
    https://github.com/Kitware/CMake/blob/
    1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/Modules/Compiler/Clang-CXX.cmake
    """
    v98 = v98gnu = v11 = v11gnu = v14 = v14gnu = v17 = v17gnu = None

    if not float(clang_version) < 2.1:
        v98 = "98"
        v98gnu = "98gnu"

    if not float(clang_version) < 3.1:
        v11 = "c++11"
        v11gnu = "gnu++11"
    elif not float(clang_version) < 2.1:
        v11 = "c++0x"
        v11gnu = "gnu++0x"

    if not float(clang_version) < 3.5:
        v14 = "c++14"
        v14gnu = "gnu++14"
    elif not float(clang_version) < 3.4:
        v14 = "c++1y"
        v14gnu = "gnu++1y"

    if not float(clang_version) < 3.5:
        v17 = "c++1z"
        v17gnu = "gnu++1z"

    flag = {"98": v98, "98gnu": v98gnu,
            "11": v11, "11gnu": v11gnu,
            "14": v14, "14gnu": v14gnu,
            "17": v17, "17gnu": v17gnu}.get(cppstd, None)
    return "-std=%s" % flag if flag else None


def _cstd_gcc(gcc_version, cstd):
    """https://github.com/Kitware/CMake/blob/1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/
    Modules/Compiler/GNU-CXX.cmake"""
    v90 = v90gnu = v99 = v99gnu = v11 = v11gnu = None

    if not float(gcc_version) < 4.5:
        v90 = "c90"
        v90gnu = "gnu90"
    elif not float(gcc_version) < 3.4:
        v90 = "c89"
        v90gnu = "gnu89"

    if not float(gcc_version) < 3.4:
        v99 = "c99"
        v99gnu = "gnu99"

    if not float(gcc_version) < 4.7:
        v11 = "c11"
        v11gnu = "gnu11"
    elif not float(gcc_version) < 4.6:
        v11 = "c1x"
        v11gnu = "gnu1x"

    flag = {"90": v90, "90gnu": v90gnu,
            "99": v99, "99gnu": v99gnu,
            "11": v11, "11gnu": v11gnu}.get(cstd)
    return "-std=%s" % flag if flag else None


def _cppstd_gcc(gcc_version, cppstd):
    """https://github.com/Kitware/CMake/blob/1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/
    Modules/Compiler/GNU-CXX.cmake"""
    v98 = v98gnu = v11 = v11gnu = v14 = v14gnu = v17 = v17gnu = None

    if not float(gcc_version) < 3.4:
        v98 = "98"
        v98gnu = "98gnu"

    if not float(gcc_version) < 4.7:
        v11 = "c++11"
        v11gnu = "gnu++11"
    elif not float(gcc_version) < 4.4:
        v11 = "c++0x"
        v11gnu = "gnu++0x"

    if not float(gcc_version) < 4.9:
        v14 = "c++14"
        v14gnu = "gnu++14"
    elif not float(gcc_version) < 4.8:
        v14 = "c++1y"
        v14gnu = "gnu++1y"

    if not float(gcc_version) < 5.1:
        v17 = "c++1z"
        v17gnu = "gnu++1z"

    flag = {"98": v98, "98gnu": v98gnu,
            "11": v11, "11gnu": v11gnu,
            "14": v14, "14gnu": v14gnu,
            "17": v17, "17gnu": v17gnu}.get(cppstd)
    return "-std=%s" % flag if flag else None


_sun_cc_libcxx_flags_dict = {"libCstd": "-library=Cstd",
                             "libstdcxx": "-library=stdcxx4",
                             "libstlport": "-library=stlport4",
                             "libstdc++": "-library=stdcpp"}
