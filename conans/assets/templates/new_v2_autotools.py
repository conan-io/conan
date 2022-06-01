import textwrap

from conans.assets.templates.new_v2_cmake import source_cpp, source_h, test_main

conanfile_lib = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.gnu import AutotoolsToolchain, Autotools
    from conan.tools.layout import basic_layout
    from conan.tools.apple import fix_apple_shared_install_name


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

        exports_sources = "configure.ac", "Makefile.am", "src/*"

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def layout(self):
            basic_layout(self)

        def generate(self):
            at_toolchain = AutotoolsToolchain(self)
            at_toolchain.generate()

        def build(self):
            autotools = Autotools(self)
            autotools.autoreconf()
            autotools.configure()
            autotools.make()

        def package(self):
            autotools = Autotools(self)
            autotools.install()
            fix_apple_shared_install_name(self)

        def package_info(self):
            self.cpp_info.libs = ["{name}"]
    """)

configure_ac = textwrap.dedent("""
    AC_INIT([{name}], [{version}], [])
    AM_INIT_AUTOMAKE([-Wall -Werror foreign])
    AC_PROG_CXX
    AM_PROG_AR
    LT_INIT
    AC_CONFIG_FILES([Makefile src/Makefile])
    AC_OUTPUT
    """)

makefile_am = textwrap.dedent("""
    SUBDIRS = src
    """)

makefile_am_lib = textwrap.dedent("""
    lib_LTLIBRARIES = lib{name}.la
    lib{name}_la_SOURCES = {name}.cpp {name}.h
    lib{name}_la_HEADERS = {name}.h
    lib{name}_ladir = $(includedir)
    """)

test_conanfile = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.gnu import Autotools
    from conan.tools.layout import basic_layout
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
            autotools = Autotools(self)
            autotools.autoreconf()
            autotools.configure()
            autotools.make()

        def layout(self):
            basic_layout(self)

        def test(self):
            if not cross_building(self):
                cmd = os.path.join(self.cpp.build.bindirs[0], "main")
                self.run(cmd, env="conanrun")
    """)

test_configure_ac = textwrap.dedent("""
    AC_INIT([main], [1.0], [])
    AM_INIT_AUTOMAKE([-Wall -Werror foreign])
    AC_PROG_CXX
    AC_PROG_RANLIB
    AM_PROG_AR
    AC_CONFIG_FILES([Makefile])
    AC_OUTPUT
    """)

test_makefile_am = textwrap.dedent("""
    bin_PROGRAMS = main
    main_SOURCES = main.cpp
    """)


def get_autotools_lib_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_lib.format(name=name, version=version,
                                                  package_name=package_name),
             "src/Makefile.am": makefile_am_lib.format(name=name, version=version),
             "src/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "src/{}.h".format(name): source_h.format(name=name, version=version),
             "configure.ac": configure_ac.format(name=name, version=version),
             "Makefile.am": makefile_am.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile.format(name=name, version=version,
                                                                package_name=package_name),
             "test_package/main.cpp": test_main.format(name=name),
             "test_package/configure.ac": test_configure_ac.format(name=name, version=version),
             "test_package/Makefile.am": test_makefile_am.format(name=name, version=version)}
    return files


conanfile_exe = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.gnu import AutotoolsToolchain, Autotools
    from conan.tools.layout import basic_layout
    from conan.tools.files import chdir


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

        # Sources are located in the same place as this recipe, copy them to the recipe
        exports_sources = "configure.ac", "Makefile.am", "src/*"

        def layout(self):
            basic_layout(self)

        def generate(self):
            at_toolchain = AutotoolsToolchain(self)
            at_toolchain.generate()

        def build(self):
            autotools = Autotools(self)
            autotools.autoreconf()
            autotools.configure()
            autotools.make()

        def package(self):
            autotools = Autotools(self)
            autotools.install()
        """)

test_conanfile_exe = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.build import cross_building
    from conan.tools.layout import basic_layout


    class {package_name}TestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        # VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
        # (it will be defined in Conan 2.0)
        generators = "VirtualRunEnv"
        apply_env = False
        test_type = "explicit"

        def requirements(self):
            self.requires(self.tested_reference_str)

        def layout(self):
            basic_layout(self)

        def test(self):
            if not cross_building(self):
                self.run("{name}", env="conanrun")
    """)

makefile_am_exe = textwrap.dedent("""
    bin_PROGRAMS = {name}
    {name}_SOURCES = main.cpp {name}.cpp {name}.h
    """)


def get_autotools_exe_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_exe.format(name=name, version=version,
                                                  package_name=package_name),
             "src/Makefile.am": makefile_am_exe.format(name=name, version=version),
             "src/main.cpp": test_main.format(name=name),
             "src/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "src/{}.h".format(name): source_h.format(name=name, version=version),
             "configure.ac": configure_ac.format(name=name, version=version),
             "Makefile.am": makefile_am.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile_exe.format(name=name, version=version,
                                                                    package_name=package_name)}
    return files
