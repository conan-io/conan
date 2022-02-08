
def cross_building(conanfile=None, skip_x64_x86=False):
    host_os = conanfile.settings.get_safe("os")
    host_arch = conanfile.settings.get_safe("arch")
    build_os = conanfile.settings_build.get_safe('os')
    build_arch = conanfile.settings_build.get_safe('arch')

    if skip_x64_x86 and host_os is not None and (build_os == host_os) and \
            host_arch is not None and ((build_arch == "x86_64") and (host_arch == "x86") or
                                       (build_arch == "sparcv9") and (host_arch == "sparc") or
                                       (build_arch == "ppc64") and (host_arch == "ppc32")):
        return False

    if host_os is not None and (build_os != host_os):
        return True
    if host_arch is not None and (build_arch != host_arch):
        return True

    return False

