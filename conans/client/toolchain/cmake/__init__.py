from conans.client.tools import cross_building
from .native import CMakeNativeToolchain
from .android import CMakeAndroidToolchain


def CMakeToolchain(conanfile, *args, **kwargs):
    if not cross_building(conanfile):
        return CMakeNativeToolchain(conanfile, *args, **kwargs)
    else:
        # Exceptions to cross-building scenarios
        if conanfile.settings.os == 'Windows' and conanfile.settings_build.os == 'Windows':
            return CMakeNativeToolchain(conanfile, *args, **kwargs)

        # Actual cross-building
        if conanfile.settings.os == 'Android':
            return CMakeAndroidToolchain(conanfile, *args, **kwargs)
