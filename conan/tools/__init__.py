from conans.model.build_info import CppInfo as _CppInfo
from conan.tools.helpers import (
    default_config_options,
    default_configure,
    default_package_id
)


def CppInfo(conanfile):
    # Creation of a CppInfo object, to decouple the creation from the actual internal location
    # that at the moment doesn't require a ``conanfile`` argument, but might require in the future
    # and allow us to refactor the location of conans.model.build_info import CppInfo
    return _CppInfo()
