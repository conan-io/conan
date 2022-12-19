from conans.errors import ConanException

CONAN_TOOLCHAIN_ARGS_FILE = "conanbuild.conf"
CONAN_TOOLCHAIN_ARGS_SECTION = "toolchain"


def _check_duplicated_generator(generator, conanfile):
    if generator.__class__.__name__ in conanfile.generators:
        raise ConanException(f"{generator.__class__.__name__} is declared in the generators "
                             "attribute, but was instantiated in the generate() method toos. "
                             "It should only be present in one of them.")
