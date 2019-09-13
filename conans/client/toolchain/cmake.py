# coding=utf-8

import os


class CMakeToolchain:
    filename = "conan.cmake"
    definitions = {}

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def dump(self, install_folder):
        with open(os.path.join(install_folder, self.filename), "w") as f:
            f.write("# Conan generated toolchain file\n")
            f.write('message(STATUS "Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")')
