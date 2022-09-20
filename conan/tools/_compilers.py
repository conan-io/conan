from conans.client.tools.apple import to_apple_arch
from conans.model.version import Version


def architecture_flag(settings):
    """
    returns flags specific to the target architecture and compiler
    """
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    arch = settings.get_safe("arch")
    the_os = settings.get_safe("os")
    subsystem = settings.get_safe("os.subsystem")
    subsystem_ios_version = settings.get_safe("os.subsystem.ios_version")
    if not compiler or not arch:
        return ""

    if the_os == "Android":
        return ""

    if str(compiler) in ['gcc', 'apple-clang', 'clang', 'sun-cc']:
        if str(the_os) == 'Macos' and str(subsystem) == 'catalyst':
            # FIXME: This might be conflicting with Autotools --target cli arg
            apple_arch = to_apple_arch(arch)
            if apple_arch:
                return '--target=%s-apple-ios%s-macabi' % (apple_arch, subsystem_ios_version)
        elif str(arch) in ['x86_64', 'sparcv9', 's390x']:
            return '-m64'
        elif str(arch) in ['x86', 'sparc']:
            return '-m32'
        elif str(arch) in ['s390']:
            return '-m31'
        elif str(the_os) == 'AIX':
            if str(arch) in ['ppc32']:
                return '-maix32'
            elif str(arch) in ['ppc64']:
                return '-maix64'
    elif str(compiler) == "intel":
        # https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-m32-m64-qm32-qm64
        if str(arch) == "x86":
            return "/Qm32" if str(compiler_base) == "Visual Studio" else "-m32"
        elif str(arch) == "x86_64":
            return "/Qm64" if str(compiler_base) == "Visual Studio" else "-m64"
    elif str(compiler) == "intel-cc":
        # https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-m32-m64-qm32-qm64
        if str(arch) == "x86":
            return "/Qm32" if the_os == "Windows" else "-m32"
        elif str(arch) == "x86_64":
            return "/Qm64" if the_os == "Windows" else "-m64"
    elif str(compiler) == "mcst-lcc":
        return {"e2k-v2": "-march=elbrus-v2",
                "e2k-v3": "-march=elbrus-v3",
                "e2k-v4": "-march=elbrus-v4",
                "e2k-v5": "-march=elbrus-v5",
                "e2k-v6": "-march=elbrus-v6",
                "e2k-v7": "-march=elbrus-v7"}.get(str(arch), "")
    return ""


def build_type_link_flags(settings):
    """
    returns link flags specific to the build type (Debug, Release, etc.)
    [-debug]
    """
    compiler = settings.get_safe("compiler")
    build_type = settings.get_safe("build_type")
    if not compiler or not build_type:
        return []

    # https://github.com/Kitware/CMake/blob/d7af8a34b67026feaee558433db3a835d6007e06/
    # Modules/Platform/Windows-MSVC.cmake
    if compiler in ["msvc", "Visual Studio"]:
        if build_type in ("Debug", "RelWithDebInfo"):
            return ["-debug"]

    return []


def build_type_flags(settings):
    """
    returns flags specific to the build type (Debug, Release, etc.)
    (-s, -g, /Zi, etc.)
    """
    compiler = settings.get_safe("compiler.base") or settings.get_safe("compiler")
    build_type = settings.get_safe("build_type")
    vs_toolset = settings.get_safe("compiler.toolset")
    if not compiler or not build_type:
        return []

    # https://github.com/Kitware/CMake/blob/d7af8a34b67026feaee558433db3a835d6007e06/
    # Modules/Platform/Windows-MSVC.cmake
    if str(compiler) in ['Visual Studio', 'msvc']:
        if vs_toolset and "clang" in str(vs_toolset):
            flags = {"Debug": ["-gline-tables-only", "-fno-inline", "-O0"],
                     "Release": ["-O2"],
                     "RelWithDebInfo": ["-gline-tables-only", "-O2", "-fno-inline"],
                     "MinSizeRel": []
                     }.get(build_type, ["-O2", "-Ob2"])
        else:
            flags = {"Debug": ["-Zi", "-Ob0", "-Od"],
                     "Release": ["-O2", "-Ob2"],
                     "RelWithDebInfo": ["-Zi", "-O2", "-Ob1"],
                     "MinSizeRel": ["-O1", "-Ob1"],
                     }.get(build_type, [])
        return flags
    else:
        # https://github.com/Kitware/CMake/blob/f3bbb37b253a1f4a26809d6f132b3996aa2e16fc/
        # Modules/Compiler/GNU.cmake
        # clang include the gnu (overriding some things, but not build type) and apple clang
        # overrides clang but it doesn't touch clang either
        if str(compiler) in ["clang", "gcc", "apple-clang", "qcc", "mcst-lcc"]:
            # FIXME: It is not clear that the "-s" is something related with the build type
            # cmake is not adjusting it
            # -s: Remove all symbol table and relocation information from the executable.
            flags = {"Debug": ["-g"],
                     "Release": ["-O3", "-s"] if str(compiler) == "gcc" else ["-O3"],
                     "RelWithDebInfo": ["-O2", "-g"],
                     "MinSizeRel": ["-Os"],
                     }.get(build_type, [])
            return flags
        elif str(compiler) == "sun-cc":
            # https://github.com/Kitware/CMake/blob/f3bbb37b253a1f4a26809d6f132b3996aa2e16fc/
            # Modules/Compiler/SunPro-CXX.cmake
            flags = {"Debug": ["-g"],
                     "Release": ["-xO3"],
                     "RelWithDebInfo": ["-xO2", "-g"],
                     "MinSizeRel": ["-xO2", "-xspace"],
                     }.get(build_type, [])
            return flags
    return ""


def use_win_mingw(conanfile):
    if hasattr(conanfile, 'settings_build'):
        os_build = conanfile.settings_build.get_safe('os')
    else:
        os_build = conanfile.settings.get_safe('os_build')
    if os_build is None:  # Assume is the same specified in host settings, not cross-building
        os_build = conanfile.settings.get_safe("os")

    if os_build == "Windows":
        compiler = conanfile.settings.get_safe("compiler")
        sub = conanfile.settings.get_safe("os.subsystem")
        if sub in ("cygwin", "msys2", "msys") or compiler == "qcc":
            return False
        else:
            return True
    return False


def cppstd_flag(settings):
    compiler = settings.get_safe("compiler")
    compiler_version = settings.get_safe("compiler.version")
    compiler_base = settings.get_safe("compiler.base")
    cppstd = settings.get_safe("compiler.cppstd")

    if not compiler or not compiler_version or not cppstd:
        return ""

    cppstd_intel = _cppstd_intel_visualstudio if compiler_base == "Visual Studio" else \
        _cppstd_intel_gcc
    func = {"gcc": _cppstd_gcc,
            "clang": _cppstd_clang,
            "apple-clang": _cppstd_apple_clang,
            "Visual Studio": _cppstd_visualstudio,
            "msvc": _cppstd_msvc,
            "intel": cppstd_intel,
            "intel-cc": _cppstd_intel_cc,
            "mcst-lcc": _cppstd_mcst_lcc}.get(str(compiler), None)
    flag = None
    if func:
        flag = func(str(compiler_version), str(cppstd))
    return flag


def _cppstd_visualstudio(visual_version, cppstd):
    # https://docs.microsoft.com/en-us/cpp/build/reference/std-specify-language-standard-version
    v14 = None
    v17 = None
    v20 = None
    v23 = None

    if Version(visual_version) >= "14":
        v14 = "c++14"
        v17 = "c++latest"
    if Version(visual_version) >= "15":
        v17 = "c++17"
        v20 = "c++latest"
    if Version(visual_version) >= "17":
        v20 = "c++20"
        v23 = "c++latest"

    flag = {"14": v14, "17": v17, "20": v20, "23": v23}.get(str(cppstd), None)
    return "/std:%s" % flag if flag else None


def _cppstd_msvc(visual_version, cppstd):
    # https://docs.microsoft.com/en-us/cpp/build/reference/std-specify-language-standard-version
    v14 = None
    v17 = None
    v20 = None
    v23 = None

    if Version(visual_version) >= "190":
        v14 = "c++14"
        v17 = "c++latest"
    if Version(visual_version) >= "191":
        v17 = "c++17"
        v20 = "c++latest"
    if Version(visual_version) >= "193":
        v20 = "c++20"
        v23 = "c++latest"

    flag = {"14": v14, "17": v17, "20": v20, "23": v23}.get(str(cppstd), None)
    return "/std:%s" % flag if flag else None


def _cppstd_apple_clang(clang_version, cppstd):
    """
    Inspired in:
    https://github.com/Kitware/CMake/blob/master/Modules/Compiler/AppleClang-CXX.cmake
    """

    v98 = vgnu98 = v11 = vgnu11 = v14 = vgnu14 = v17 = vgnu17 = v20 = vgnu20 = None

    if Version(clang_version) >= "4.0":
        v98 = "c++98"
        vgnu98 = "gnu++98"
        v11 = "c++11"
        vgnu11 = "gnu++11"

    if Version(clang_version) >= "6.1":
        v14 = "c++14"
        vgnu14 = "gnu++14"
    elif Version(clang_version) >= "5.1":
        v14 = "c++1y"
        vgnu14 = "gnu++1y"

    if Version(clang_version) >= "6.1":
        v17 = "c++1z"
        vgnu17 = "gnu++1z"

    if Version(clang_version) >= "9.1":
        # Not confirmed that it didn't work before 9.1 but 1z is still valid, so we are ok
        v17 = "c++17"
        vgnu17 = "gnu++17"

    if Version(clang_version) >= "10.0":
        v20 = "c++2a"
        vgnu20 = "gnu++2a"

    flag = {"98": v98, "gnu98": vgnu98,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20}.get(cppstd, None)

    return "-std=%s" % flag if flag else None


def _cppstd_clang(clang_version, cppstd):
    """
    Inspired in:
    https://github.com/Kitware/CMake/blob/
    1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/Modules/Compiler/Clang-CXX.cmake

    https://clang.llvm.org/cxx_status.html
    """
    v98 = vgnu98 = v11 = vgnu11 = v14 = vgnu14 = v17 = vgnu17 = v20 = vgnu20 = v23 = vgnu23 = None

    if Version(clang_version) >= "2.1":
        v98 = "c++98"
        vgnu98 = "gnu++98"

    if Version(clang_version) >= "3.1":
        v11 = "c++11"
        vgnu11 = "gnu++11"
    elif Version(clang_version) >= "2.1":
        v11 = "c++0x"
        vgnu11 = "gnu++0x"

    if Version(clang_version) >= "3.5":
        v14 = "c++14"
        vgnu14 = "gnu++14"
    elif Version(clang_version) >= "3.4":
        v14 = "c++1y"
        vgnu14 = "gnu++1y"

    if Version(clang_version) >= "5":
        v17 = "c++17"
        vgnu17 = "gnu++17"
    elif Version(clang_version) >= "3.5":
        v17 = "c++1z"
        vgnu17 = "gnu++1z"

    if Version(clang_version) >= "6":
        v20 = "c++2a"
        vgnu20 = "gnu++2a"

    if Version(clang_version) >= "12":
        v20 = "c++20"
        vgnu20 = "gnu++20"

        v23 = "c++2b"
        vgnu23 = "gnu++2b"

    flag = {"98": v98, "gnu98": vgnu98,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20,
            "23": v23, "gnu23": vgnu23}.get(cppstd, None)
    return "-std=%s" % flag if flag else None


def _cppstd_gcc(gcc_version, cppstd):
    """https://github.com/Kitware/CMake/blob/master/Modules/Compiler/GNU-CXX.cmake"""
    # https://gcc.gnu.org/projects/cxx-status.html
    v98 = vgnu98 = v11 = vgnu11 = v14 = vgnu14 = v17 = vgnu17 = v20 = vgnu20 = v23 = vgnu23 = None

    if Version(gcc_version) >= "3.4":
        v98 = "c++98"
        vgnu98 = "gnu++98"

    if Version(gcc_version) >= "4.7":
        v11 = "c++11"
        vgnu11 = "gnu++11"
    elif Version(gcc_version) >= "4.3":
        v11 = "c++0x"
        vgnu11 = "gnu++0x"

    if Version(gcc_version) >= "4.9":
        v14 = "c++14"
        vgnu14 = "gnu++14"
    elif Version(gcc_version) >= "4.8":
        v14 = "c++1y"
        vgnu14 = "gnu++1y"

    if Version(gcc_version) >= "5":
        v17 = "c++1z"
        vgnu17 = "gnu++1z"

    if Version(gcc_version) >= "5.2":  # Not sure if even in 5.1 gnu17 is valid, but gnu1z is
        v17 = "c++17"
        vgnu17 = "gnu++17"

    if Version(gcc_version) >= "8":
        v20 = "c++2a"
        vgnu20 = "gnu++2a"

    if Version(gcc_version) >= "11":
        v23 = "c++2b"
        vgnu23 = "gnu++2b"

    flag = {"98": v98, "gnu98": vgnu98,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20,
            "23": v23, "gnu23": vgnu23}.get(cppstd)
    return "-std=%s" % flag if flag else None


def _cppstd_intel_common(intel_version, cppstd, vgnu98, vgnu0x):
    # https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-std-qstd
    # https://software.intel.com/en-us/articles/intel-cpp-compiler-release-notes
    # NOTE: there are only gnu++98 and gnu++0x, and only for Linux/macOS
    v98 = v11 = v14 = v17 = v20 = None
    vgnu11 = vgnu14 = vgnu17 = vgnu20 = None

    if Version(intel_version) >= "12":
        v11 = "c++0x"
        vgnu11 = vgnu0x
    if Version(intel_version) >= "14":
        v11 = "c++11"
        vgnu11 = vgnu0x
    if Version(intel_version) >= "16":
        v14 = "c++14"
    if Version(intel_version) >= "18":
        v17 = "c++17"
    if Version(intel_version) >= "19.1":
        v20 = "c++20"

    return {"98": v98, "gnu98": vgnu98,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20}.get(cppstd)


def _cppstd_intel_gcc(intel_version, cppstd):
    flag = _cppstd_intel_common(intel_version, cppstd, "gnu++98", "gnu++0x")
    return "-std=%s" % flag if flag else None


def _cppstd_intel_visualstudio(intel_version, cppstd):
    flag = _cppstd_intel_common(intel_version, cppstd, None, None)
    return "/Qstd=%s" % flag if flag else None


def _cppstd_mcst_lcc(mcst_lcc_version, cppstd):
    v11 = vgnu11 = v14 = vgnu14 = v17 = vgnu17 = v20 = vgnu20 = None

    if Version(mcst_lcc_version) >= "1.21":
        v11 = "c++11"
        vgnu11 = "gnu++11"
        v14 = "c++14"
        vgnu14 = "gnu++14"

    if Version(mcst_lcc_version) >= "1.24":
        v17 = "c++17"
        vgnu17 = "gnu++17"

    if Version(mcst_lcc_version) >= "1.25":
        v20 = "c++2a"
        vgnu20 = "gnu++2a"

    flag = {"98": "c++98", "gnu98": "gnu++98",
            "03": "c++03", "gnu03": "gnu++03",
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20}.get(cppstd)
    return "-std=%s" % flag if flag else None


def _cppstd_intel_cc(_, cppstd):
    """
    Inspired in:
    https://software.intel.com/content/www/us/en/develop/documentation/
    oneapi-dpcpp-cpp-compiler-dev-guide-and-reference/top/compiler-reference/
    compiler-options/compiler-option-details/language-options/std-qstd.html
    """
    # Note: for now, we don't care about compiler version
    v98 = "c++98"
    vgnu98 = "gnu++98"
    v03 = "c++03"
    vgnu03 = "gnu++03"
    v11 = "c++11"
    vgnu11 = "gnu++11"
    v14 = "c++14"
    vgnu14 = "gnu++14"
    v17 = "c++17"
    vgnu17 = "gnu++17"
    v20 = "c++20"
    vgnu20 = "gnu++20"
    v23 = "c++2b"
    vgnu23 = "gnu++2b"

    flag = {"98": v98, "gnu98": vgnu98,
            "03": v03, "gnu03": vgnu03,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20,
            "23": v23, "gnu23": vgnu23}.get(cppstd, None)
    return "-std=%s" % flag if flag else None
