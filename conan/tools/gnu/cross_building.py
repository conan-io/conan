from conan.tools.gnu.get_cross_building_settings import _get_cross_building_settings


def _cross_building(conanfile, self_os=None, self_arch=None, skip_x64_x86=False):
    ret = _get_cross_building_settings(conanfile, self_os, self_arch)

    build_os, build_arch, host_os, host_arch = ret

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
