from conan.tools.cmake.cmakedeps import FIND_MODE_MODULE, FIND_MODE_BOTH


def is_multi_configuration(generator):
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator or "Multi-Config" in generator

