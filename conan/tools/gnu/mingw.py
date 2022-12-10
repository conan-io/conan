def is_mingw(conanfile):
    """
    Validate if current compiler in host setttings is related to MinGW
    :param conanfile: ConanFile instance
    :return: True, if the host compiler is related to MinGW, otherwise False.
    """
    host_os = conanfile.settings.get_safe("os")
    host_subsystem = conanfile.settings.get_safe("os.subsystem")
    is_windows_native = host_os == "Windows" and host_subsystem not in ["cygwin", "wsl"]
    host_compiler = conanfile.settings.get_safe("compiler")
    is_mingw_gcc = is_windows_native and host_compiler == "gcc"
    is_mingw_clang = is_windows_native and host_compiler == "clang" and \
                     not conanfile.settings.get_safe("compiler.runtime")
    return is_mingw_gcc or is_mingw_clang
