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
