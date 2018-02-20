from conans.model.version import Version


def available_cppstd_versions(compiler, compiler_version):
    ret = []
    stds = ["98", "98gnu", "11", "11gnu", "14",  "14gnu", "17", "17gnu"]
    for stdver in stds:
        if cppstd_flag(compiler, compiler_version, stdver):
            ret.append(stdver)
    return ret


def cppstd_flag(compiler, compiler_version, cppstd):
    if not compiler or not compiler_version or not cppstd:
        return ""
    func = {"gcc": _cppstd_gcc,
            "clang": _cppstd_clang,
            "apple-clang": _cppstd_apple_clang,
            "Visual Studio": _cppstd_visualstudio}.get(str(compiler), None)
    flag = None
    if func:
        flag = func(str(compiler_version), str(cppstd))
    return flag


def cppstd_default(compiler, compiler_version):

    default = {"gcc": _gcc_cppstd_default(compiler_version),
               "clang": "gnu++98",
               "apple-clang": "gnu++98",
               "Visual Studio": _visual_cppstd_default(compiler_version)}.get(str(compiler), None)
    return default


def _gcc_cppstd_default(compiler_version):

    return "98gnu" if Version(compiler_version) < "6.1" else "14gnu"


def _visual_cppstd_default(compiler_version):
    if Version(compiler_version) >= "14":  # VS 2015 update 3 only
        return "14"
    return None


def _cppstd_visualstudio(visual_version, cppstd):

    v14 = None
    v17 = None

    if Version(visual_version) >= "14":
        v14 = "c++14"
        v17 = "c++latest"
    if Version(visual_version) >= "15":
        v17 = "c++17"

    flag = {"14": v14, "17": v17}.get(str(cppstd), None)
    return "/std:%s" % flag if flag else None


def _cppstd_apple_clang(clang_version, cppstd):
    """
    Inspired in:
    https://github.com/Kitware/CMake/blob/master/Modules/Compiler/AppleClang-CXX.cmake
    """

    v98 = v98gnu = v11 = v11gnu = v14 = v14gnu = v17 = v17gnu = None

    if Version(clang_version) >= "4.0":
        v98 = "c++98"
        v98gnu = "gnu++98"
        v11 = "c++11"
        v11gnu = "gnu++11"

    if Version(clang_version) >= "6.1":
        v14 = "c++14"
        v14gnu = "gnu++14"
    elif Version(clang_version) >= "5.1":
        v14 = "c++1y"
        v14gnu = "gnu++1y"

    if Version(clang_version) >= "6.1":
        v17 = "c++1z"
        v17gnu = "gnu++1z"

    flag = {"98": v98, "98gnu": v98gnu,
            "11": v11, "11gnu": v11gnu,
            "14": v14, "14gnu": v14gnu,
            "17": v17, "17gnu": v17gnu}.get(cppstd, None)

    return "-std=%s" % flag if flag else None


def _cppstd_clang(clang_version, cppstd):
    """
    Inspired in:
    https://github.com/Kitware/CMake/blob/
    1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/Modules/Compiler/Clang-CXX.cmake
    """
    v98 = v98gnu = v11 = v11gnu = v14 = v14gnu = v17 = v17gnu = None

    if Version(clang_version) >= "2.1":
        v98 = "c++98"
        v98gnu = "gnu++98"

    if Version(clang_version) >= "3.1":
        v11 = "c++11"
        v11gnu = "gnu++11"
    elif Version(clang_version) >= "2.1":
        v11 = "c++0x"
        v11gnu = "gnu++0x"

    if Version(clang_version) >= "3.5":
        v14 = "c++14"
        v14gnu = "gnu++14"
        v17 = "c++1z"
        v17gnu = "gnu++1z"
    elif Version(clang_version) >= "3.4":
        v14 = "c++1y"
        v14gnu = "gnu++1y"

    flag = {"98": v98, "98gnu": v98gnu,
            "11": v11, "11gnu": v11gnu,
            "14": v14, "14gnu": v14gnu,
            "17": v17, "17gnu": v17gnu}.get(cppstd, None)
    return "-std=%s" % flag if flag else None


def _cppstd_gcc(gcc_version, cppstd):
    """https://github.com/Kitware/CMake/blob/master/Modules/Compiler/GNU-CXX.cmake"""
    # https://gcc.gnu.org/projects/cxx-status.html#cxx98
    v98 = v98gnu = v11 = v11gnu = v14 = v14gnu = v17 = v17gnu = None

    if Version(gcc_version) >= "3.4":
        v98 = "c++98"
        v98gnu = "gnu++98"

    if Version(gcc_version) >= "4.7":
        v11 = "c++11"
        v11gnu = "gnu++11"
    elif Version(gcc_version) >= "4.3":
        v11 = "c++0x"
        v11gnu = "gnu++0x"

    if Version(gcc_version) >= "4.9":
        v14 = "c++14"
        v14gnu = "gnu++14"
    elif Version(gcc_version) >= "4.8":
        v14 = "c++1y"
        v14gnu = "gnu++1y"

    if Version(gcc_version) >= "5.1":
        v17 = "c++1z"
        v17gnu = "gnu++1z"

    flag = {"98": v98, "98gnu": v98gnu,
            "11": v11, "11gnu": v11gnu,
            "14": v14, "14gnu": v14gnu,
            "17": v17, "17gnu": v17gnu}.get(cppstd)
    return "-std=%s" % flag if flag else None
