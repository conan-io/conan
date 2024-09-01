from conans.model.version import Version


def architecture_flag(settings):
    """
    returns flags specific to the target architecture and compiler
    Used by CMakeToolchain and AutotoolsToolchain
    """
    from conan.tools.apple.apple import _to_apple_arch
    compiler = settings.get_safe("compiler")
    arch = settings.get_safe("arch")
    the_os = settings.get_safe("os")
    subsystem = settings.get_safe("os.subsystem")
    subsystem_ios_version = settings.get_safe("os.subsystem.ios_version")
    if not compiler or not arch:
        return ""

    if the_os == "Android":
        return ""

    if compiler == "clang" and the_os == "Windows":
        # LLVM/Clang and VS/Clang must define runtime. msys2 clang won't
        runtime = settings.get_safe("compiler.runtime")  # runtime is Windows only
        if runtime is not None:
            return ""
        # TODO: Maybe Clang-Mingw runtime does, but with C++ is impossible to test
        return {"x86_64": "-m64",
                "x86": "-m32"}.get(arch, "")
    elif compiler in ['gcc', 'apple-clang', 'clang', 'sun-cc']:
        if the_os == 'Macos' and subsystem == 'catalyst':
            # FIXME: This might be conflicting with Autotools --target cli arg
            apple_arch = _to_apple_arch(arch)
            if apple_arch:
                # TODO: Could we define anything like `to_apple_target()`?
                #       Check https://github.com/rust-lang/rust/issues/48862
                return f'--target={apple_arch}-apple-ios{subsystem_ios_version}-macabi'
        elif arch in ['x86_64', 'sparcv9', 's390x']:
            return '-m64'
        elif arch in ['x86', 'sparc']:
            return '-m32'
        elif arch in ['s390']:
            return '-m31'
        elif arch in ['tc131', 'tc16', 'tc161', 'tc162', 'tc18']:
            return '-m{}'.format(arch)
        elif the_os == 'AIX':
            if arch in ['ppc32']:
                return '-maix32'
            elif arch in ['ppc64']:
                return '-maix64'
    elif compiler == "intel-cc":
        # https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-m32-m64-qm32-qm64
        if arch == "x86":
            return "/Qm32" if the_os == "Windows" else "-m32"
        elif arch == "x86_64":
            return "/Qm64" if the_os == "Windows" else "-m64"
    elif compiler == "mcst-lcc":
        return {"e2k-v2": "-march=elbrus-v2",
                "e2k-v3": "-march=elbrus-v3",
                "e2k-v4": "-march=elbrus-v4",
                "e2k-v5": "-march=elbrus-v5",
                "e2k-v6": "-march=elbrus-v6",
                "e2k-v7": "-march=elbrus-v7"}.get(arch, "")
    return ""


def libcxx_flags(conanfile):
    libcxx = conanfile.settings.get_safe("compiler.libcxx")
    if not libcxx:
        return None, None
    compiler = conanfile.settings.get_safe("compiler")
    lib = stdlib11 = None
    if compiler == "apple-clang":
        # In apple-clang 2 only values atm are "libc++" and "libstdc++"
        lib = f'-stdlib={libcxx}'
    elif compiler == "clang" or compiler == "intel-cc":
        if libcxx == "libc++":
            lib = "-stdlib=libc++"
        elif libcxx == "libstdc++" or libcxx == "libstdc++11":
            lib = "-stdlib=libstdc++"
        # FIXME, something to do with the other values? Android c++_shared?
    elif compiler == "sun-cc":
        lib = {"libCstd": "-library=Cstd",
               "libstdcxx": "-library=stdcxx4",
               "libstlport": "-library=stlport4",
               "libstdc++": "-library=stdcpp"
               }.get(libcxx)
    elif compiler == "qcc":
        lib = f'-Y _{libcxx}'

    if compiler in ['clang', 'apple-clang', 'gcc']:
        if libcxx == "libstdc++":
            stdlib11 = "_GLIBCXX_USE_CXX11_ABI=0"
        elif libcxx == "libstdc++11" and conanfile.conf.get("tools.gnu:define_libcxx11_abi",
                                                            check_type=bool):
            stdlib11 = "_GLIBCXX_USE_CXX11_ABI=1"
    return lib, stdlib11


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
    if compiler == "msvc":
        if build_type in ("Debug", "RelWithDebInfo"):
            return ["-debug"]

    return []


def build_type_flags(settings):
    """
    returns flags specific to the build type (Debug, Release, etc.)
    (-s, -g, /Zi, etc.)
    Used only by AutotoolsToolchain
    """
    compiler = settings.get_safe("compiler")
    build_type = settings.get_safe("build_type")
    vs_toolset = settings.get_safe("compiler.toolset")
    if not compiler or not build_type:
        return []

    # https://github.com/Kitware/CMake/blob/d7af8a34b67026feaee558433db3a835d6007e06/
    # Modules/Platform/Windows-MSVC.cmake
    if compiler == "msvc":
        if vs_toolset and "clang" in vs_toolset:
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
        if compiler in ["clang", "gcc", "apple-clang", "qcc", "mcst-lcc"]:
            flags = {"Debug": ["-g"],
                     "Release": ["-O3"],
                     "RelWithDebInfo": ["-O2", "-g"],
                     "MinSizeRel": ["-Os"],
                     }.get(build_type, [])
            return flags
        elif compiler == "sun-cc":
            # https://github.com/Kitware/CMake/blob/f3bbb37b253a1f4a26809d6f132b3996aa2e16fc/
            # Modules/Compiler/SunPro-CXX.cmake
            flags = {"Debug": ["-g"],
                     "Release": ["-xO3"],
                     "RelWithDebInfo": ["-xO2", "-g"],
                     "MinSizeRel": ["-xO2", "-xspace"],
                     }.get(build_type, [])
            return flags
    return []


def cppstd_flag(conanfile) -> str:
    """
    Returns flags specific to the C++ standard based on the ``conanfile.settings.compiler``,
    ``conanfile.settings.compiler.version`` and ``conanfile.settings.compiler.cppstd``.

    It also considers when using GNU extension in ``settings.compiler.cppstd``, reflecting it in the
    compiler flag. Currently, it supports GCC, Clang, AppleClang, MSVC, Intel, MCST-LCC.

    In case there is no ``settings.compiler`` or ``settings.cppstd`` in the profile, the result will
    be an **empty string**.

    :param conanfile: The current recipe object. Always use ``self``.
    :return: ``str`` with the standard C++ flag used by the compiler. e.g. "-std=c++11", "/std:c++latest"
    """
    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    cppstd = conanfile.settings.get_safe("compiler.cppstd")

    if not compiler or not compiler_version or not cppstd:
        return ""

    func = {"gcc": _cppstd_gcc,
            "clang": _cppstd_clang,
            "apple-clang": _cppstd_apple_clang,
            "msvc": _cppstd_msvc,
            "intel-cc": _cppstd_intel_cc,
            "mcst-lcc": _cppstd_mcst_lcc}.get(compiler)
    flag = None
    if func:
        flag = func(Version(compiler_version), str(cppstd))
    return flag


def cppstd_msvc_flag(visual_version, cppstd):
    # https://docs.microsoft.com/en-us/cpp/build/reference/std-specify-language-standard-version
    if cppstd == "23":
        if visual_version >= "193":
            return "c++latest"
    elif cppstd == "20":
        if visual_version >= "192":
            return "c++20"
        elif visual_version >= "191":
            return "c++latest"
    elif cppstd == "17":
        if visual_version >= "191":
            return "c++17"
        elif visual_version >= "190":
            return "c++latest"
    elif cppstd == "14":
        if visual_version >= "190":
            return "c++14"

    return None


def _cppstd_msvc(visual_version, cppstd):
    flag = cppstd_msvc_flag(visual_version, cppstd)
    return f'/std:{flag}' if flag else None


def _cppstd_apple_clang(clang_version, cppstd):
    """
    Inspired in:
    https://github.com/Kitware/CMake/blob/master/Modules/Compiler/AppleClang-CXX.cmake
    """

    v98 = vgnu98 = v11 = vgnu11 = v14 = vgnu14 = v17 = vgnu17 = v20 = vgnu20 = v23 = vgnu23 = None

    if clang_version >= "4.0":
        v98 = "c++98"
        vgnu98 = "gnu++98"
        v11 = "c++11"
        vgnu11 = "gnu++11"

    if clang_version >= "6.1":
        v14 = "c++14"
        vgnu14 = "gnu++14"
    elif clang_version >= "5.1":
        v14 = "c++1y"
        vgnu14 = "gnu++1y"

    # Not confirmed that it didn't work before 9.1 but 1z is still valid, so we are ok
    # Note: cmake allows c++17 since version 10.0
    if clang_version >= "9.1":
        v17 = "c++17"
        vgnu17 = "gnu++17"
    elif clang_version >= "6.1":
        v17 = "c++1z"
        vgnu17 = "gnu++1z"

    if clang_version >= "13.0":
        v20 = "c++20"
        vgnu20 = "gnu++20"
    elif clang_version >= "10.0":
        v20 = "c++2a"
        vgnu20 = "gnu++2a"

    if clang_version >= "13.0":
        v23 = "c++2b"
        vgnu23 = "gnu++2b"

    flag = {"98": v98, "gnu98": vgnu98,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20,
            "23": v23, "gnu23": vgnu23}.get(cppstd)

    return f'-std={flag}' if flag else None


def _cppstd_clang(clang_version, cppstd):
    """
    Inspired in:
    https://github.com/Kitware/CMake/blob/
    1fe2dc5ef2a1f262b125a2ba6a85f624ce150dd2/Modules/Compiler/Clang-CXX.cmake

    https://clang.llvm.org/cxx_status.html
    """
    v98 = vgnu98 = v11 = vgnu11 = v14 = vgnu14 = v17 = vgnu17 = v20 = vgnu20 = v23 = vgnu23 = None

    if clang_version >= "2.1":
        v98 = "c++98"
        vgnu98 = "gnu++98"

    if clang_version >= "3.1":
        v11 = "c++11"
        vgnu11 = "gnu++11"
    elif clang_version >= "2.1":
        v11 = "c++0x"
        vgnu11 = "gnu++0x"

    if clang_version >= "3.5":
        v14 = "c++14"
        vgnu14 = "gnu++14"
    elif clang_version >= "3.4":
        v14 = "c++1y"
        vgnu14 = "gnu++1y"

    if clang_version >= "5":
        v17 = "c++17"
        vgnu17 = "gnu++17"
    elif clang_version >= "3.5":
        v17 = "c++1z"
        vgnu17 = "gnu++1z"

    if clang_version >= "6":
        v20 = "c++2a"
        vgnu20 = "gnu++2a"

    if clang_version >= "12":
        v20 = "c++20"
        vgnu20 = "gnu++20"

        v23 = "c++2b"
        vgnu23 = "gnu++2b"

    if clang_version >= "17":
        v23 = "c++23"
        vgnu23 = "gnu++23"

    flag = {"98": v98, "gnu98": vgnu98,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20,
            "23": v23, "gnu23": vgnu23}.get(cppstd)
    return f'-std={flag}' if flag else None


def _cppstd_gcc(gcc_version, cppstd):
    """https://github.com/Kitware/CMake/blob/master/Modules/Compiler/GNU-CXX.cmake"""
    # https://gcc.gnu.org/projects/cxx-status.html
    v98 = vgnu98 = v11 = vgnu11 = v14 = vgnu14 = v17 = vgnu17 = v20 = vgnu20 = v23 = vgnu23 = None

    if gcc_version >= "3.4":
        v98 = "c++98"
        vgnu98 = "gnu++98"

    if gcc_version >= "4.7":
        v11 = "c++11"
        vgnu11 = "gnu++11"
    elif gcc_version >= "4.3":
        v11 = "c++0x"
        vgnu11 = "gnu++0x"

    if gcc_version >= "4.9":
        v14 = "c++14"
        vgnu14 = "gnu++14"
    elif gcc_version >= "4.8":
        v14 = "c++1y"
        vgnu14 = "gnu++1y"

    if gcc_version >= "5":
        v17 = "c++1z"
        vgnu17 = "gnu++1z"

    if gcc_version >= "5.2":  # Not sure if even in 5.1 gnu17 is valid, but gnu1z is
        v17 = "c++17"
        vgnu17 = "gnu++17"

    if gcc_version >= "8":
        v20 = "c++2a"
        vgnu20 = "gnu++2a"

    if gcc_version >= "11":
        v23 = "c++2b"
        vgnu23 = "gnu++2b"

    if gcc_version >= "12":
        v20 = "c++20"
        vgnu20 = "gnu++20"

    flag = {"98": v98, "gnu98": vgnu98,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20,
            "23": v23, "gnu23": vgnu23}.get(cppstd)
    return f'-std={flag}' if flag else None


def _cppstd_intel_common(intel_version, cppstd, vgnu98, vgnu0x):
    # https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-std-qstd
    # https://software.intel.com/en-us/articles/intel-cpp-compiler-release-notes
    # NOTE: there are only gnu++98 and gnu++0x, and only for Linux/macOS
    v98 = v11 = v14 = v17 = v20 = None
    vgnu11 = vgnu14 = vgnu17 = vgnu20 = None

    if intel_version >= "12":
        v11 = "c++0x"
        vgnu11 = vgnu0x
    if intel_version >= "14":
        v11 = "c++11"
        vgnu11 = vgnu0x
    if intel_version >= "16":
        v14 = "c++14"
    if intel_version >= "18":
        v17 = "c++17"
    if intel_version >= "19.1":
        v20 = "c++20"

    return {"98": v98, "gnu98": vgnu98,
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20}.get(cppstd)


def _cppstd_intel_gcc(intel_version, cppstd):
    flag = _cppstd_intel_common(intel_version, cppstd, "gnu++98", "gnu++0x")
    return f'-std={flag}' if flag else None


def _cppstd_intel_visualstudio(intel_version, cppstd):
    flag = _cppstd_intel_common(intel_version, cppstd, None, None)
    return f'/Qstd={flag}' if flag else None


def _cppstd_mcst_lcc(mcst_lcc_version, cppstd):
    v11 = vgnu11 = v14 = vgnu14 = v17 = vgnu17 = v20 = vgnu20 = None

    if mcst_lcc_version >= "1.21":
        v11 = "c++11"
        vgnu11 = "gnu++11"
        v14 = "c++14"
        vgnu14 = "gnu++14"

    if mcst_lcc_version >= "1.24":
        v17 = "c++17"
        vgnu17 = "gnu++17"

    if mcst_lcc_version >= "1.25":
        v20 = "c++2a"
        vgnu20 = "gnu++2a"

    # FIXME: What is this "03"?? that is not a valid cppstd in the settings.yml
    flag = {"98": "c++98", "gnu98": "gnu++98",
            "03": "c++03", "gnu03": "gnu++03",
            "11": v11, "gnu11": vgnu11,
            "14": v14, "gnu14": vgnu14,
            "17": v17, "gnu17": vgnu17,
            "20": v20, "gnu20": vgnu20}.get(cppstd)
    return f'-std={flag}' if flag else None


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
            "23": v23, "gnu23": vgnu23}.get(cppstd)
    return f'-std={flag}' if flag else None


def cstd_flag(conanfile) -> str:
    """
    Returns flags specific to the C+standard based on the ``conanfile.settings.compiler``,
    ``conanfile.settings.compiler.version`` and ``conanfile.settings.compiler.cstd``.

    It also considers when using GNU extension in ``settings.compiler.cstd``, reflecting it in the
    compiler flag. Currently, it supports GCC, Clang, AppleClang, MSVC, Intel, MCST-LCC.

    In case there is no ``settings.compiler`` or ``settings.cstd`` in the profile, the result will
    be an **empty string**.

    :param conanfile: The current recipe object. Always use ``self``.
    :return: ``str`` with the standard C flag used by the compiler.
    """
    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    cstd = conanfile.settings.get_safe("compiler.cstd")

    if not compiler or not compiler_version or not cstd:
        return ""

    func = {"gcc": _cstd_gcc,
            "clang": _cstd_clang,
            "apple-clang": _cstd_apple_clang,
            "msvc": _cstd_msvc}.get(compiler)
    flag = None
    if func:
        flag = func(Version(compiler_version), str(cstd))
    return flag


def _cstd_gcc(gcc_version, cstd):
    # TODO: Verify flags per version
    flag = {"99": "c99",
            "11": "c11",
            "17": "c17",
            "23": "c23"}.get(cstd, cstd)
    return f'-std={flag}' if flag else None


def _cstd_clang(gcc_version, cstd):
    # TODO: Verify flags per version
    flag = {"99": "c99",
            "11": "c11",
            "17": "c17",
            "23": "c23"}.get(cstd, cstd)
    return f'-std={flag}' if flag else None


def _cstd_apple_clang(gcc_version, cstd):
    # TODO: Verify flags per version
    flag = {"99": "c99",
            "11": "c11",
            "17": "c17",
            "23": "c23"}.get(cstd, cstd)
    return f'-std={flag}' if flag else None


def cstd_msvc_flag(visual_version, cstd):
    if cstd == "17":
        if visual_version >= "192":
            return "c17"
    elif cstd == "11":
        if visual_version >= "192":
            return "c11"
    return None


def _cstd_msvc(visual_version, cstd):
    flag = cstd_msvc_flag(visual_version, cstd)
    return f'/std:{flag}' if flag else None
