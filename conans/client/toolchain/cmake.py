# coding=utf-8

import os
import textwrap
from jinja2 import Template

# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


class CMakeToolchain:
    filename = "conan.cmake"
    definitions = {}

    _template = textwrap.dedent("""
        # Conan generated toolchain file
        message(INFO "Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")

        # Host machine        
        set(CMAKE_SYSTEM_NAME {{host.os}})
        set(CMAKE_SYSTEM_VERSION {{host.os_version}})
        set(CMAKE_SYSTEM_PROCESSOR {{host.arch}})

        # Build machine (only if different)
        set(CMAKE_HOST_SYSTEM_NAME {{build.os}})
        set(CMAKE_HOST_SYSTEM_VERSION {{build.os_version}})
        set(CMAKE_HOST_SYSTEM_PROCESSOR {{build.arch}})
        
        set(CMAKE_C_COMPILER {{c_compiler}})
        set(CMAKE_CXX_COMPILER {{cxx_compiler}})
    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def dump(self, install_folder):
        with open(os.path.join(install_folder, self.filename), "w") as f:
            # TODO: I need the profile_host and profile_build here!
            # TODO: What if the compiler is a build require?
            # TODO: Add all the stuff related to settings (ALL settings or just _MY_ settings?)
            # TODO: I would want to have here the path to the compiler too
            compiler = "clang" if self._conanfile.settings.compiler == "apple-clang" else self._conanfile.settings.compiler
            context = {"os": self._conanfile.settings.os,
                       "arch": self._conanfile.settings.arch,
                       "c_compiler": compiler,
                       "cxx_compiler": compiler+'++'}

            t = Template(self._template)
            content = t.render(**context)

            f.write(content)
            f.write("\n\n# ")
            f.write('set(CMAKE_MODULE_PATH "{}")\n'.format(install_folder))  # CMAKE_MODULE_PATH can depend on the configuration (different FindXXX.cmake files provided),
                                                                             #  it should be ok to define it into the toolchain file

            # TODO: Remove this, intended only for testing
            f.write('set(ENV{TOOLCHAIN_ENV} "toolchain_environment")\n')
            f.write('set(TOOLCHAIN_VAR "toolchain_variable")\n')
