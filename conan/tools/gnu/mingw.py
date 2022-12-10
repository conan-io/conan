def is_mingw(conanfile):
    """
    Validate if current compiler in host setttings is related to MinGW
    :param conanfile: ConanFile instance
    :return: True, if the host compiler is related to MinGW, otherwise False.
    """
    host_os = conanfile.settings.get_safe("os")
    host_subsystem = conanfile.settings.get_safe("os.subsystem")
    is_wsl = host_os == "Windows" and host_subsystem == "wsl"
    is_cygwin = host_os == "Windows" and host_subsystem == "cygwin"
    host_compiler = conanfile.settings.get_safe("compiler")
    is_mingw_gcc = host_os == "Windows" and not (is_wsl or is_cygwin) and host_compiler == "gcc"
    is_mingw_clang = host_os == "Windows" and not (is_wsl or is_cygwin) and host_compiler == "clang" and \
                     not conanfile.settings.get_safe("compiler.runtime")
    return is_mingw_gcc or is_mingw_clang
