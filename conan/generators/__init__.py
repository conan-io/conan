# noinspection PyUnresolvedReferences

from conans.client.generators.cmake_find_package_multi import CMakeFindPackageMultiGenerator \
    as CMakeGenerator
# TODO: We need a ``generators = "cmake_xxxx" simple name for migration to Conan 2.0
# We need to evolve this generator for Conan 2.0 here, probably a copy,
# doing all breaking changes before 2.0
