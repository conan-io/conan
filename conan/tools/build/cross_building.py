
def cross_building(conanfile=None, skip_x64_x86=False):

    build_os, build_arch, host_os, host_arch = get_cross_building_settings(conanfile)

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


def get_cross_building_settings(conanfile):
    # FIXME: Develop2 this shouldn't go in develop2 where the build settings always exists
    #        Keep the current develop2 implementation for the whole module while merging
    os_host = conanfile.settings.get_safe("os")
    arch_host = conanfile.settings.get_safe("arch")

    if hasattr(conanfile, 'settings_build'):
        return (conanfile.settings_build.get_safe('os'), conanfile.settings_build.get_safe('arch'),
                os_host, arch_host)
    else:
        return os_host, arch_host, os_host, arch_host


def can_run(conanfile):
    """
    Validates if the current build platform can run a file which is not for same arch
    See https://github.com/conan-io/conan/issues/11035
    """
    allowed = conanfile.conf.get("tools.build.cross_building:can_run", check_type=bool)
    if allowed is None:
        return not cross_building(conanfile)
    return allowed
