from conans.client.tools import cross_building
from .native import CMakeNativeToolchain
from .android import CMakeAndroidToolchain


def CMakeToolchain(conanfile, **kwargs):
    if not cross_building(conanfile):
        return CMakeNativeToolchain(conanfile=conanfile, **kwargs)
    else:
        # Exceptions to cross-building scenarios
        if conanfile.settings.os == 'Windows' and conanfile.settings_build.os == 'Windows':
            return CMakeNativeToolchain(conanfile=conanfile, **kwargs)

        # Actual cross-building
        if conanfile.settings.os == 'Android':
            return CMakeAndroidToolchain(conanfile=conanfile, **kwargs)
