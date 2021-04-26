import warnings
from collections import namedtuple

from conan.tools.oss.get_cross_building_settings import get_cross_building_settings
from conans.errors import ConanException


def cross_building(conanfile=None, self_os=None, self_arch=None, skip_x64_x86=False, settings=None):
    # Handle input arguments (backwards compatibility with 'settings' as first argument)
    # TODO: This can be promoted to a decorator pattern for tools if we adopt 'conanfile' as the
    #   first argument for all of them.
    if conanfile and settings:
        raise ConanException("Do not set both arguments, 'conanfile' and 'settings',"
                             " to call cross_building function")

    from conans.model.conan_file import ConanFile
    if conanfile and not isinstance(conanfile, ConanFile):
        return cross_building(settings=conanfile, self_os=self_os, self_arch=self_arch,
                              skip_x64_x86=skip_x64_x86)

    if settings:
        warnings.warn("Argument 'settings' has been deprecated, use 'conanfile' instead")

    if conanfile:
        ret = get_cross_building_settings(conanfile, self_os, self_arch)
    else:
        # TODO: If Conan is using 'profile_build' here we don't have any information about it,
        #   we are falling back to the old behavior (which is probably wrong here)
        conanfile = namedtuple('_ConanFile', ['settings'])(settings)
        ret = get_cross_building_settings(conanfile, self_os, self_arch)

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
