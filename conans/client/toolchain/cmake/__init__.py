from conans.client.tools import cross_building
from conans.errors import ConanException
from .android import CMakeAndroidToolchain
from .native import CMakeNativeToolchain


def CMakeToolchain(conanfile, *args, **kwargs):
    skip_x64_x86 = conanfile.settings.get_safe('os') in ['Windows', 'Linux']
    if not cross_building(conanfile, skip_x64_x86=skip_x64_x86):
        return CMakeNativeToolchain(conanfile, *args, **kwargs)
    else:
        os_ = conanfile.settings.get_safe('os')
        if os_ == 'Android':
            return CMakeAndroidToolchain(conanfile, *args, **kwargs)
        else:
            # TODO: We need to provide a way to inject a toolchain from the outside
            raise ConanException("No toolchain available to cross-compile to 'os={}'".format(os_))
