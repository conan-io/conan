import textwrap

conanfile_sources_v2 = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.gnu import AutotoolsToolchain, Autotools
    from conan.tools.layout import basic_layout


    class {package_name}Conan(ConanFile):
        name = "{name}"
        version = "{version}"

        # Optional metadata
        license = "<Put the package license here>"
        author = "<Put your name here> <And your email here>"
        url = "<Package recipe repository url here, for issues about the package>"
        description = "<Description of {package_name} here>"
        topics = ("<Put some tag here>", "<here>", "<and here>")

        # Binary configuration
        settings = "os", "compiler", "build_type", "arch"
        options = {{"shared": [True, False], "fPIC": [True, False]}}
        default_options = {{"shared": False, "fPIC": True}}

        exports_sources = "configure.ac", "Makefile.am", "src/*", "include/*"

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def layout(self):
            basic_layout(self, src_folder="source")

        def generate(self):
            at_toolchain = AutotoolsToolchain(self)
            at_toolchain.generate()

        def build(self):
            autotools = Autotools(self)
            autotools.configure()
            autotools.make()

        def package(self):
            autotools = Autotools(self)
            autotools.install()

        def package_info(self):
            self.cpp_info.libs = ["{name}"]
    """)

source_h = textwrap.dedent("""#pragma once

    #ifdef _WIN32
      #define {name}_EXPORT __declspec(dllexport)
    #else
      #define {name}_EXPORT
    #endif

    {name}_EXPORT void {name}();
    """)

source_cpp = textwrap.dedent("""#include <iostream>
    #include "{name}.h"

    void {name}(){{
        #ifdef NDEBUG
        std::cout << "{name}/{version}: Hello World Release!\n";
        #else
        std::cout << "{name}/{version}: Hello World Debug!\n";
        #endif

        // ARCHITECTURES
        #ifdef _M_X64
        std::cout << "  {name}/{version}: _M_X64 defined\n";
        #endif

        #ifdef _M_IX86
        std::cout << "  {name}/{version}: _M_IX86 defined\n";
        #endif

        #if __i386__
        std::cout << "  {name}/{version}: __i386__ defined\n";
        #endif

        #if __x86_64__
        std::cout << "  {name}/{version}: __x86_64__ defined\n";
        #endif

        // Libstdc++
        #if defined _GLIBCXX_USE_CXX11_ABI
        std::cout << "  {name}/{version}: _GLIBCXX_USE_CXX11_ABI "<< _GLIBCXX_USE_CXX11_ABI << "\n";
        #endif

        // COMPILER VERSIONS
        #if _MSC_VER
        std::cout << "  {name}/{version}: _MSC_VER" << _MSC_VER<< "\n";
        #endif

        #if _MSVC_LANG
        std::cout << "  {name}/{version}: _MSVC_LANG" << _MSVC_LANG<< "\n";
        #endif

        #if __cplusplus
        std::cout << "  {name}/{version}: __cplusplus" << __cplusplus<< "\n";
        #endif

        #if __INTEL_COMPILER
        std::cout << "  {name}/{version}: __INTEL_COMPILER" << __INTEL_COMPILER<< "\n";
        #endif

        #if __GNUC__
        std::cout << "  {name}/{version}: __GNUC__" << __GNUC__<< "\n";
        #endif

        #if __GNUC_MINOR__
        std::cout << "  {name}/{version}: __GNUC_MINOR__" << __GNUC_MINOR__<< "\n";
        #endif

        #if __clang_major__
        std::cout << "  {name}/{version}: __clang_major__" << __clang_major__<< "\n";
        #endif

        #if __clang_minor__
        std::cout << "  {name}/{version}: __clang_minor__" << __clang_minor__<< "\n";
        #endif

        #if __apple_build_version__
        std::cout << "  {name}/{version}: __apple_build_version__" << __apple_build_version__<< "\n";
        #endif

        // SUBSYSTEMS

        #if __MSYS__
        std::cout << "  {name}/{version}: __MSYS__" << __MSYS__<< "\n";
        #endif

        #if __MINGW32__
        std::cout << "  {name}/{version}: __MINGW32__" << __MINGW32__<< "\n";
        #endif

        #if __MINGW64__
        std::cout << "  {name}/{version}: __MINGW64__" << __MINGW64__<< "\n";
        #endif

        #if __CYGWIN__
        std::cout << "  {name}/{version}: __CYGWIN__" << __CYGWIN__<< "\n";
        #endif
    }}
    """)


test_main = textwrap.dedent("""
    #include "{name}.h"

    int main() {{
        {name}();
    }}
    """)

configure_ac = textwrap.dedent("""
    AC_INIT([main], [1.0], [some@email.com])
    AM_INIT_AUTOMAKE([-Wall -Werror foreign])
    AC_PROG_CXX
    AC_PROG_RANLIB
    AM_PROG_AR
    AC_CONFIG_FILES([Makefile])
    AC_OUTPUT
    """)

makefile_am = textwrap.dedent("""
    bin_PROGRAMS = main
    main_SOURCES = ./src/main.cpp
    """)


def get_autotools_lib_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_sources_v2.format(name=name, version=version,
                                                         package_name=package_name),
             "src/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "include/{}.h".format(name): source_h.format(name=name, version=version),
             "configure.ac": configure_ac,
             "Makefile.am": makefile_am,
             }
    return files
