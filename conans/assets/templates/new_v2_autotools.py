import textwrap

conanfile_sources_v2 = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.gnu import AutotoolsToolchain, Autotools


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

        exports_sources = "configure.ac", "Makefile.am", "{name}.cpp", "{name}.h"

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def layout(self):
            self.folders.build = "."
            self.folders.generators = os.path.join(self.folders.build, "conan")
            self.cpp.build.bindirs = ["."]
            self.cpp.build.libdirs = ["."]
            self.folders.source = "."

        def generate(self):
            at_toolchain = AutotoolsToolchain(self)
            at_toolchain.generate()

        def build(self):
            self.run("aclocal")
            self.run("autoconf")
            self.run("automake --add-missing --foreign")
            autotools = Autotools(self)
            autotools.configure()
            autotools.make()

        def package(self):
            autotools = Autotools(self)
            autotools.install()

        def package_info(self):
            self.cpp_info.libs = ["{name}"]
    """)

source_h = textwrap.dedent("""
    #pragma once

    #ifdef _WIN32
      #define {name}_EXPORT __declspec(dllexport)
    #else
      #define {name}_EXPORT
    #endif

    {name}_EXPORT void {name}();
    """)

source_cpp = textwrap.dedent("""
    #include <iostream>
    #include "{name}.h"

    void {name}(){{
        #ifdef NDEBUG
        std::cout << "{name}/{version}: Hello World Release!" << std::endl;
        #else
        std::cout << "{name}/{version}: Hello World Debug!" << std::endl;
        #endif

        // ARCHITECTURES
        #ifdef _M_X64
        std::cout << "  {name}/{version}: _M_X64 defined" << std::endl;
        #endif

        #ifdef _M_IX86
        std::cout << "  {name}/{version}: _M_IX86 defined" << std::endl;
        #endif

        #if __i386__
        std::cout << "  {name}/{version}: __i386__ defined" << std::endl;
        #endif

        #if __x86_64__
        std::cout << "  {name}/{version}: __x86_64__ defined" << std::endl;
        #endif

        // Libstdc++
        #if defined _GLIBCXX_USE_CXX11_ABI
        std::cout << "  {name}/{version}: _GLIBCXX_USE_CXX11_ABI "<< _GLIBCXX_USE_CXX11_ABI <<  << std::endl;
        #endif

        // COMPILER VERSIONS
        #if _MSC_VER
        std::cout << "  {name}/{version}: _MSC_VER" << _MSC_VER << std::endl;
        #endif

        #if _MSVC_LANG
        std::cout << "  {name}/{version}: _MSVC_LANG" << _MSVC_LANG << std::endl;
        #endif

        #if __cplusplus
        std::cout << "  {name}/{version}: __cplusplus" << __cplusplus << std::endl;
        #endif

        #if __INTEL_COMPILER
        std::cout << "  {name}/{version}: __INTEL_COMPILER" << __INTEL_COMPILER << std::endl;
        #endif

        #if __GNUC__
        std::cout << "  {name}/{version}: __GNUC__" << __GNUC__ << std::endl;
        #endif

        #if __GNUC_MINOR__
        std::cout << "  {name}/{version}: __GNUC_MINOR__" << __GNUC_MINOR__ << std::endl;
        #endif

        #if __clang_major__
        std::cout << "  {name}/{version}: __clang_major__" << __clang_major__ << std::endl;
        #endif

        #if __clang_minor__
        std::cout << "  {name}/{version}: __clang_minor__" << __clang_minor__ << std::endl;
        #endif

        #if __apple_build_version__
        std::cout << "  {name}/{version}: __apple_build_version__" << __apple_build_version__ << std::endl;
        #endif

        // SUBSYSTEMS

        #if __MSYS__
        std::cout << "  {name}/{version}: __MSYS__" << __MSYS__ << std::endl;
        #endif

        #if __MINGW32__
        std::cout << "  {name}/{version}: __MINGW32__" << __MINGW32__ << std::endl;
        #endif

        #if __MINGW64__
        std::cout << "  {name}/{version}: __MINGW64__" << __MINGW64__ << std::endl;
        #endif

        #if __CYGWIN__
        std::cout << "  {name}/{version}: __CYGWIN__" << __CYGWIN__ << std::endl;
        #endif
    }}
    """)

configure_ac = textwrap.dedent("""
    AC_INIT([{name}], [{version}], [])
    AM_INIT_AUTOMAKE([-Wall -Werror foreign])
    AC_PROG_CXX
    AC_PROG_RANLIB
    AM_PROG_AR
    AC_CONFIG_FILES([Makefile])
    AC_OUTPUT
    """)

makefile_am = textwrap.dedent("""
    lib_LIBRARIES = lib{name}.a
    lib{name}_a_SOURCES = {name}.cpp {name}.h
    include_HEADERS = {name}.h
    """)

test_conanfile = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.gnu import AutotoolsToolchain, Autotools, AutotoolsDeps
    from conan.tools.build import cross_building


    class {package_name}TestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        # VirtualBuildEnv and VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
        # (it will be defined in Conan 2.0)
        generators = "AutotoolsDeps", "AutotoolsToolchain", "VirtualBuildEnv", "VirtualRunEnv"
        apply_env = False
        test_type = "explicit"

        def requirements(self):
            self.requires(self.tested_reference_str)

        def build(self):
            self.run("aclocal")
            self.run("autoconf")
            self.run("automake --add-missing --foreign")
            autotools = Autotools(self)
            autotools.configure()
            autotools.make()

        def layout(self):
            self.folders.build = "."
            self.folders.generators = os.path.join(self.folders.build, "conan")
            self.cpp.build.bindirs = ["."]
            self.cpp.build.libdirs = ["."]
            self.folders.source = "."

        def test(self):
            if not cross_building(self):
                cmd = os.path.join(self.cpp.build.bindirs[0], "example")
                self.run(cmd, env="conanrun")
    """)

test_example = textwrap.dedent("""
    #include "{name}.h"

    int main() {{
        {name}();
    }}
    """)

test_configure_ac = textwrap.dedent("""
    AC_INIT([example], [1.0], [])
    AM_INIT_AUTOMAKE([-Wall -Werror foreign])
    AC_PROG_CXX
    AC_PROG_RANLIB
    AM_PROG_AR
    AC_CONFIG_FILES([Makefile])
    AC_OUTPUT
    """)

test_makefile_am = textwrap.dedent("""
    bin_PROGRAMS = example
    example_SOURCES = example.cpp
    """)


def get_autotools_lib_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_sources_v2.format(name=name, version=version,
                                                         package_name=package_name),
             "{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "{}.h".format(name): source_h.format(name=name, version=version),
             "configure.ac": configure_ac.format(name=name, version=version),
             "Makefile.am": makefile_am.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile.format(name=name, version=version,
                                                                package_name=package_name),
             "test_package/example.cpp": test_example.format(name=name),
             "test_package/configure.ac": test_configure_ac.format(name=name, version=version),
             "test_package/Makefile.am": test_makefile_am.format(name=name, version=version),
             }
    return files
