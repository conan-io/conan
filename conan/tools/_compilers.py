def architecture_flag(settings):
    """
    returns flags specific to the target architecture and compiler
    """
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    arch = settings.get_safe("arch")
    the_os = settings.get_safe("os")
    subsystem = settings.get_safe("os.subsystem")
    if not compiler or not arch:
        return ""

    if str(compiler) in ['gcc', 'apple-clang', 'clang', 'sun-cc']:
        if str(the_os) == 'Macos' and str(subsystem) == 'catalyst' and str(arch) == 'x86_64':
            # FIXME: This might be conflicting with Autotools --target cli arg
            return '--target=x86_64-apple-ios-macabi'
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
    elif str(compiler) == "mcst-lcc":
        return {"e2k-v2": "-march=elbrus-v2",
                "e2k-v3": "-march=elbrus-v3",
                "e2k-v4": "-march=elbrus-v4",
                "e2k-v5": "-march=elbrus-v5",
                "e2k-v6": "-march=elbrus-v6",
                "e2k-v7": "-march=elbrus-v7"}.get(str(arch), "")
    return ""


def build_type_flags(settings):
    """
    returns flags specific to the build type (Debug, Release, etc.)
    (-s, -g, /Zi, etc.)
    """
    compiler = settings.get_safe("compiler.base") or settings.get_safe("compiler")

    build_type = settings.get_safe("build_type")
    vs_toolset = settings.get_safe("compiler.toolset")
    if not compiler or not build_type:
        return ""

    # https://github.com/Kitware/CMake/blob/d7af8a34b67026feaee558433db3a835d6007e06/
    # Modules/Platform/Windows-MSVC.cmake
    if str(compiler) == 'Visual Studio':
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
