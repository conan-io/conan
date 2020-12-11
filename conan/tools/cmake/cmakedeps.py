# We need to evolve this generator for Conan 2.0 here, probably a copy,
# doing all breaking changes before 2.0

# Necessary to circumvent import errors
def CMakeDeps(conanfile):
    from conans.client.generators.cmake_find_package_multi import CMakeFindPackageMultiGenerator
    return CMakeFindPackageMultiGenerator(conanfile)
