

def cross_building(conanfile):
    ret = get_cross_building_settings(conanfile)

    build_os, build_arch, host_os, host_arch = ret

    if host_os is not None and (build_os != host_os):
        return True
    if host_arch is not None and (build_arch != host_arch):
        return True

    return False


def get_cross_building_settings(conanfile):
    os_host = conanfile.settings.get_safe("os")
    arch_host = conanfile.settings.get_safe("arch")

    if hasattr(conanfile, 'settings_build'):
        return (conanfile.settings_build.get_safe('os'),
                conanfile.settings_build.get_safe('arch'),
                os_host,
                arch_host)
    else:
        return (os_host,
                arch_host,
                os_host,
                arch_host)
