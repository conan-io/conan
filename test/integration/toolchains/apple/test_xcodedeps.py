import os
import platform
import re
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from test.integration.toolchains.apple.test_xcodetoolchain import _get_filename
from conan.test.utils.tools import TestClient

_expected_dep_xconfig = [
    "SYSTEM_HEADER_SEARCH_PATHS = $(inherited) $(SYSTEM_HEADER_SEARCH_PATHS_{name}_{name})",
    "GCC_PREPROCESSOR_DEFINITIONS = $(inherited) $(GCC_PREPROCESSOR_DEFINITIONS_{name}_{name})",
    "OTHER_CFLAGS = $(inherited) $(OTHER_CFLAGS_{name}_{name})",
    "OTHER_CPLUSPLUSFLAGS = $(inherited) $(OTHER_CPLUSPLUSFLAGS_{name}_{name})",
    "FRAMEWORK_SEARCH_PATHS = $(inherited) $(FRAMEWORK_SEARCH_PATHS_{name}_{name})",
    "LIBRARY_SEARCH_PATHS = $(inherited) $(LIBRARY_SEARCH_PATHS_{name}_{name})",
    "OTHER_LDFLAGS = $(inherited) $(OTHER_LDFLAGS_{name}_{name})",
]

_expected_conf_xconfig = [
    "SYSTEM_HEADER_SEARCH_PATHS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "GCC_PREPROCESSOR_DEFINITIONS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "OTHER_CFLAGS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "OTHER_CPLUSPLUSFLAGS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "FRAMEWORK_SEARCH_PATHS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "LIBRARY_SEARCH_PATHS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "OTHER_LDFLAGS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = "
]


def expected_files(current_folder, configuration, architecture, sdk_version):
    files = []
    name = _get_filename(configuration, architecture, sdk_version)
    deps = ["hello", "goodbye"]
    files.extend(
        [os.path.join(current_folder, "conan_{dep}_{dep}{name}.xcconfig".format(dep=dep, name=name)) for dep in deps])
    files.append(os.path.join(current_folder, "conandeps.xcconfig"))
    return files


def check_contents(client, deps, configuration, architecture, sdk_version):
    for dep_name in deps:
        dep_xconfig = client.load("conan_{dep}_{dep}.xcconfig".format(dep=dep_name))
        conf_name = "conan_{}_{}{}.xcconfig".format(dep_name, dep_name,
                                                 _get_filename(configuration, architecture, sdk_version))

        assert '#include "{}"'.format(conf_name) in dep_xconfig
        for var in _expected_dep_xconfig:
            line = var.format(name=dep_name)
            assert line in dep_xconfig

        conan_conf = client.load(conf_name)
        for var in _expected_conf_xconfig:
            assert var.format(name=dep_name, configuration=configuration, architecture=architecture,
                              sdk="macosx", sdk_version=sdk_version) in conan_conf


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_generator_files():
    client = TestClient()
    client.save({"hello.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                           .with_package_info(cpp_info={"libs": ["hello"],
                                                                        "frameworks": ['framework_hello']},
                                                              env_info={})})
    client.run("export hello.py --name=hello --version=0.1")
    client.save({"goodbye.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                             .with_package_info(cpp_info={"libs": ["goodbye"],
                                                                          "frameworks": ['framework_goodbye']},
                                                                env_info={})})
    client.run("export goodbye.py --name=goodbye --version=0.1")
    client.save({"conanfile.txt": "[requires]\nhello/0.1\ngoodbye/0.1\n"}, clean_first=True)

    for build_type in ["Release", "Debug"]:

        client.run("install . -g XcodeDeps -s build_type={} -s arch=x86_64 -s os.sdk_version=12.1 --build missing".format(build_type))

        for config_file in expected_files(client.current_folder, build_type, "x86_64", "12.1"):
            assert os.path.isfile(config_file)

        conandeps = client.load("conandeps.xcconfig")
        assert '#include "conan_hello.xcconfig"' in conandeps
        assert '#include "conan_goodbye.xcconfig"' in conandeps

        conan_config = client.load("conan_config.xcconfig")
        assert '#include "conandeps.xcconfig"' in conan_config

        check_contents(client, ["hello", "goodbye"], build_type, "x86_64", "12.1")


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_generator_files_with_custom_config():
    client = TestClient()

    client.save({"hello.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                           .with_package_info(cpp_info={"libs": ["hello"]},
                                                              env_info={})})
    client.run("export hello.py --name=hello --version=0.1")

    client.save({"goodbye.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                             .with_package_info(cpp_info={"libs": ["goodbye"]},
                                                                env_info={})})
    client.run("export goodbye.py --name=goodbye --version=0.1")

    conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.apple import XcodeDeps
        class LibConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            options = {"XcodeConfigName": [None, "ANY"]}
            default_options = {"XcodeConfigName": None}
            requires = "hello/0.1", "goodbye/0.1"

            def generate(self):
                xcode = XcodeDeps(self)
                if self.options.get_safe("XcodeConfigName"):
                    xcode.configuration = str(self.options.get_safe("XcodeConfigName"))
                xcode.generate()
        """)

    client.save({"conanfile.py": conanfile_py})
    custom_config_name = "CustomConfig"

    for use_custom_config in [True, False]:
        for build_type in ["Release", "Debug"]:
            cli_command = "install . -s build_type={} -s arch=x86_64 -s os.sdk_version=12.1  --build missing".format(build_type)
            if use_custom_config:
                cli_command += " -o XcodeConfigName={}".format(custom_config_name)
                configuration_name = custom_config_name
            else:
                configuration_name = build_type

            client.run(cli_command)

            for config_file in expected_files(client.current_folder, configuration_name, "x86_64", "12.1"):
                assert os.path.isfile(config_file)

            conandeps = client.load("conandeps.xcconfig")
            assert '#include "conan_hello.xcconfig"' in conandeps
            assert '#include "conan_goodbye.xcconfig"' in conandeps

            conan_config = client.load("conan_config.xcconfig")
            assert '#include "conandeps.xcconfig"' in conan_config

            check_contents(client, ["hello", "goodbye"],  configuration_name, "x86_64", "12.1",)

@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_xcodedeps_aggregate_components():
    client = TestClient()

    conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        class LibConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.includedirs = ["liba_include"]
        """)

    client.save({"conanfile.py": conanfile_py})

    client.run("create . --name=liba --version=1.0")

    r""""
        1   a
       / \ /
      2   3
       \ /
        4   5  6
        |   |  /
         \ / /
           7
    """

    conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        class LibConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "liba/1.0"
            def package_info(self):
                self.cpp_info.components["libb_comp1"].includedirs = ["libb_comp1"]
                self.cpp_info.components["libb_comp1"].libdirs = ["mylibdir"]
                self.cpp_info.components["libb_comp2"].includedirs = ["libb_comp2"]
                self.cpp_info.components["libb_comp2"].libdirs = ["mylibdir"]
                self.cpp_info.components["libb_comp2"].requires = ["libb_comp1"]
                self.cpp_info.components["libb_comp3"].includedirs = ["libb_comp3"]
                self.cpp_info.components["libb_comp3"].libdirs = ["mylibdir"]
                self.cpp_info.components["libb_comp3"].requires = ["libb_comp1", "liba::liba"]
                self.cpp_info.components["libb_comp4"].includedirs = ["libb_comp4"]
                self.cpp_info.components["libb_comp4"].libdirs = ["mylibdir"]
                self.cpp_info.components["libb_comp4"].requires = ["libb_comp2", "libb_comp3"]
                self.cpp_info.components["libb_comp5"].includedirs = ["libb_comp5"]
                self.cpp_info.components["libb_comp5"].libdirs = ["mylibdir"]
                self.cpp_info.components["libb_comp6"].includedirs = ["libb_comp6"]
                self.cpp_info.components["libb_comp6"].libdirs = ["mylibdir"]
                self.cpp_info.components["libb_comp7"].includedirs = ["libb_comp7"]
                self.cpp_info.components["libb_comp7"].libdirs = ["mylibdir"]
                self.cpp_info.components["libb_comp7"].requires = ["libb_comp4", "libb_comp5", "libb_comp6"]
        """)

    client.save({"conanfile.py": conanfile_py})

    client.run("create . --name=libb --version=1.0")

    client.run("install --requires=libb/1.0 -g XcodeDeps")

    lib_entry = client.load("conan_libb.xcconfig")

    for index in range(1, 8):
        assert f"conan_libb_libb_comp{index}.xcconfig" in lib_entry

    component7_entry = client.load("conan_libb_libb_comp7.xcconfig")
    assert '#include "conan_liba.xcconfig"' in component7_entry

    arch_setting = client.get_default_host_profile().settings['arch']
    arch = "arm64" if arch_setting == "armv8" else arch_setting

    component7_vars = client.load(f"conan_libb_libb_comp7_release_{arch}.xcconfig")

    # all of the transitive required components and the component itself are added
    for index in range(1, 8):
        assert f"libb_comp{index}" in component7_vars

    assert "mylibdir" in component7_vars

    component4_vars = client.load(f"conan_libb_libb_comp4_release_{arch}.xcconfig")

    # all of the transitive required components and the component itself are added
    for index in range(1, 5):
        assert f"libb_comp{index}" in component4_vars

    for index in range(5, 8):
        assert f"libb_comp{index}" not in component4_vars

    # folders are aggregated
    assert "mylibdir" in component4_vars


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_xcodedeps_traits():
    client = TestClient()
    conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        class LibConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            {package_info}
            {requirements}
        """)

    package_info = """
    def package_info(self):
        self.cpp_info.components["cmp1"].includedirs = ["cmp1_includedir"]
        self.cpp_info.components["cmp2"].includedirs = ["cmp2_includedir"]

        self.cpp_info.components["cmp1"].libdirs = ["cmp1_libdir"]
        self.cpp_info.components["cmp2"].libdirs = ["cmp2_libdir"]
        self.cpp_info.components["cmp1"].libs = ["cmp1_lib"]
        self.cpp_info.components["cmp2"].libs = ["cmp2_lib"]
        self.cpp_info.components["cmp1"].system_libs = ["cmp1_system_lib"]
        self.cpp_info.components["cmp2"].system_libs = ["cmp2_system_lib"]
        self.cpp_info.components["cmp1"].frameworkdirs = ["cmp1_frameworkdir"]
        self.cpp_info.components["cmp2"].frameworkdirs = ["cmp2_frameworkdir"]
        self.cpp_info.components["cmp1"].frameworks = ["cmp1_framework"]
        self.cpp_info.components["cmp2"].frameworks = ["cmp2_framework"]

        self.cpp_info.components["cmp1"].defines = ["cmp1_define"]
        self.cpp_info.components["cmp2"].defines = ["cmp2_define"]
        self.cpp_info.components["cmp1"].cflags = ["cmp1_cflag"]
        self.cpp_info.components["cmp2"].cflags = ["cmp2_cflag"]
        self.cpp_info.components["cmp1"].cxxflags = ["cmp1_cxxflag"]
        self.cpp_info.components["cmp2"].cxxflags = ["cmp2_cxxflag"]
        self.cpp_info.components["cmp1"].sharedlinkflags = ["cmp1_sharedlinkflag"]
        self.cpp_info.components["cmp2"].sharedlinkflags = ["cmp2_sharedlinkflag"]
        self.cpp_info.components["cmp1"].exelinkflags = ["cmp1_exelinkflag"]
        self.cpp_info.components["cmp2"].exelinkflags = ["cmp2_exelinkflag"]
        """

    client.save({"lib_a.py": conanfile_py.format(requirements="", package_info=package_info)})

    client.run("create lib_a.py --name=lib_a --version=1.0")

    requirements = """
    def requirements(self):
        self.requires("lib_a/1.0", headers=False)
    """

    client.save({"lib_b.py": conanfile_py.format(requirements=requirements, package_info="")},
                clean_first=True)

    client.run("install lib_b.py -g XcodeDeps")

    arch_setting = client.get_default_host_profile().settings['arch']
    arch = "arm64" if arch_setting == "armv8" else arch_setting

    comp1_info = client.load(f"conan_lib_a_cmp1_release_{arch}.xcconfig")
    comp2_info = client.load(f"conan_lib_a_cmp2_release_{arch}.xcconfig")

    assert "cmp1_include" not in comp1_info
    assert "cmp2_include" not in comp2_info

    requirements = """
    def requirements(self):
        self.requires("lib_a/1.0", libs=False)
    """

    client.save({"lib_b.py": conanfile_py.format(requirements=requirements, package_info="")},
                clean_first=True)
    client.run("install lib_b.py -g XcodeDeps")

    comp1_info = client.load(f"conan_lib_a_cmp1_release_{arch}.xcconfig")
    comp2_info = client.load(f"conan_lib_a_cmp2_release_{arch}.xcconfig")

    assert "cmp1_frameworkdir" not in comp1_info
    assert "cmp2_frameworkdir" not in comp2_info

    assert "-lcmp1_lib -lcmp1_system_lib -framework cmp1_framework" not in comp1_info
    assert "-lcmp2_lib -lcmp2_system_lib -framework cmp2_framework" not in comp2_info

    requirements = """
    def requirements(self):
        self.requires("lib_a/1.0", headers=False, libs=False)
    """

    client.save({"lib_b.py": conanfile_py.format(requirements=requirements, package_info="")},
                clean_first=True)
    client.run("install lib_b.py -g XcodeDeps")

    # this changed from non-existing to existing after https://github.com/conan-io/conan/pull/15128
    existing = [f"conan_lib_a_cmp1_release_{arch}.xcconfig", "conan_lib_a_cmp1.xcconfig",
                    f"conan_lib_a_cmp2_release_{arch}.xcconfig", "conan_lib_a_cmp2.xcconfig",
                    "conan_lib_a.xcconfig"]

    for file in existing:
        assert os.path.exists(os.path.join(client.current_folder, file))

    assert '#include "conan_lib_a.xcconfig"' in client.load("conandeps.xcconfig")

    requirements = """
    def requirements(self):
        self.requires("lib_a/1.0", headers=False, libs=False, run=True)
    """

    client.save({"lib_b.py": conanfile_py.format(requirements=requirements, package_info="")},
                clean_first=True)

    client.run("install lib_b.py -g XcodeDeps")

    comp1_info = client.load(f"conan_lib_a_cmp1_release_{arch}.xcconfig")
    comp2_info = client.load(f"conan_lib_a_cmp2_release_{arch}.xcconfig")

    assert "cmp1_define" not in comp1_info
    assert "cmp2_define" not in comp2_info
    assert "cmp1_cflag" not in comp1_info
    assert "cmp2_cflag" not in comp2_info
    assert "cmp1_cxxflag" not in comp1_info
    assert "cmp2_cxxflag" not in comp2_info
    assert "cmp1_sharedlinkflag" not in comp1_info
    assert "cmp2_sharedlinkflag" not in comp2_info
    assert "cmp1_exelinkflag" not in comp1_info
    assert "cmp2_exelinkflag" not in comp2_info


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_xcodedeps_frameworkdirs():
    client = TestClient()

    conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        class LibConan(ConanFile):
            name = "lib_a"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.frameworkdirs = ["lib_a_frameworkdir"]
        """)

    client.save({"conanfile.py": conanfile_py})
    client.run("create .")

    arch_setting = client.get_default_host_profile().settings['arch']
    arch = "arm64" if arch_setting == "armv8" else arch_setting

    client.run("install --requires=lib_a/1.0 -g XcodeDeps")

    lib_a_xcconfig = client.load(f"conan_lib_a_lib_a_release_{arch}.xcconfig")

    assert "lib_a_frameworkdir" in lib_a_xcconfig


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_xcodedeps_cppinfo_requires():

    """
    lib_a: has four components cmp1, cmp2, cmp3, cmp4
    lib_b --> uses libA cmp1 so cpp_info.requires = ["lib_a::cmp1"]
    lib_c --> uses libA cmp2 so cpp_info.requires = ["lib_a::cmp2"]
    consumer --> libB, libC
    """
    client = TestClient()
    lib_a = textwrap.dedent("""
        from conan import ConanFile
        class lib_aConan(ConanFile):
            name = "lib_a"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.components["cmp1"].includedirs = ["include"]
                self.cpp_info.components["cmp2"].includedirs = ["include"]
                self.cpp_info.components["cmp3"].includedirs = ["include"]
                self.cpp_info.components["cmp4"].includedirs = ["include"]
        """)

    lib = textwrap.dedent("""
        from conan import ConanFile
        class lib_{name}Conan(ConanFile):
            name = "lib_{name}"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def requirements(self):
                self.requires("lib_a/1.0")
            def package_info(self):
                self.cpp_info.requires = {cppinfo_comps}
        """)

    consumer = textwrap.dedent("""
    from conan import ConanFile
    class ConsumerConan(ConanFile):
        name = "consumer"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        generators = "XcodeDeps"
        def requirements(self):
            self.requires("lib_b/1.0")
            self.requires("lib_c/1.0")
    """)

    client.save({
        'lib_a/conanfile.py': lib_a,
        'lib_b/conanfile.py': lib.format(name="b", cppinfo_comps='["lib_a::cmp1"]'),
        'lib_c/conanfile.py': lib.format(name="c", cppinfo_comps='["lib_a::cmp2"]'),
        'consumer/conanfile.py': consumer,
    })

    client.run("create lib_a")

    client.run("create lib_b")

    client.run("create lib_c")

    client.run("install consumer")

    """
    Check that the generated lib_b and lib_c xcconfig only use the cmp1 and cmp2 components
    So we will only link against the components specified in the cpp_info.requires of lib_b and lib_c
    """

    lib_b = client.load(os.path.join("consumer", "conan_lib_b_lib_b.xcconfig"))

    # check that nothing from other components than the specified in the cpp_info.requires
    # from lib_b and lib_c exist in the xcconfig that adds the includes from components
    assert "cmp1" in lib_b
    assert "cmp2" not in lib_b
    assert "cmp3" not in lib_b
    assert "cmp4" not in lib_b

    lib_c = client.load(os.path.join("consumer", "conan_lib_c_lib_c.xcconfig"))

    assert "cmp1" not in lib_c
    assert "cmp2" in lib_c
    assert "cmp3" not in lib_c
    assert "cmp4" not in lib_c


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_dependency_of_dependency_components():
    # testing: https://github.com/conan-io/conan/pull/11772

    """
    When a dependency of a dependency would have components, only the default
    name conan_dep_dep.xconfig would be included. However, this file was never
    generated, as they are in the form conan_dep_component.xconfig.

    lib_a -> lib_b -> lib_c (with components)
    """
    client = TestClient()
    lib_a = GenConanfile("lib_a", "1.0").with_require("lib_b/1.0").with_settings("os", "arch", "build_type", "compiler")
    lib_b = GenConanfile("lib_b", "1.0").with_require("lib_c/1.0").with_settings("os", "arch", "build_type", "compiler")

    lib_c = textwrap.dedent("""
        from conan import ConanFile
        class lib_aConan(ConanFile):
            name = "lib_c"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.components["cmp1"].includedirs = ["include_cmp1"]
                self.cpp_info.components["cmp2"].includedirs = ["include_cmp2"]
        """)

    client.save({
        'conanfile.py': lib_a,
        'lib_b/conanfile.py': lib_b,
        'lib_c/conanfile.py': lib_c,
    })

    client.run("create lib_c")

    client.run("create lib_b")

    client.run("install . -g XcodeDeps")

    lib_b_xconfig = client.load("conan_lib_b_lib_b.xcconfig")

    assert '#include "conan_lib_c_cmp1.xcconfig"' in lib_b_xconfig
    assert '#include "conan_lib_c_cmp1.xcconfig"' in lib_b_xconfig
    assert '#include "conan_lib_c_lib_c.xcconfig"' not in lib_b_xconfig


def test_skipped_not_included():
    # https://github.com/conan-io/conan/issues/13818
    client = TestClient()
    pkg_info = {"components": {"component": {"defines": ["SOMEDEFINE"]}}}

    client.save({"dep/conanfile.py": GenConanfile().with_package_type("header-library")
                                                   .with_package_info(cpp_info=pkg_info,
                                                                      env_info={}),
                 "pkg/conanfile.py": GenConanfile().with_requirement("dep/0.1")
                                                   .with_package_type("library")
                                                   .with_shared_option(),
                 "consumer/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                        .with_settings("os", "build_type", "arch")})
    client.run("create dep --name=dep --version=0.1")
    client.run("create pkg --name=pkg --version=0.1")
    client.run("install consumer -g XcodeDeps -s arch=x86_64 -s build_type=Release")
    assert re.search(r"Skipped binaries\n\s+(.*?)", client.out, re.DOTALL)
    dep_xconfig = client.load("consumer/conan_pkg_pkg.xcconfig")
    assert "conan_dep.xcconfig" not in dep_xconfig


def test_correctly_handle_transitive_components():
    # https://github.com/conan-io/conan/issues/14887
    client = TestClient()
    has_components = textwrap.dedent("""
        from conan import ConanFile
        class PkgWithComponents(ConanFile):
            name = 'has_components'
            version = '1.0'
            settings = 'os', 'compiler', 'arch', 'build_type'
            def package_info(self):
                self.cpp_info.components['first'].libs = ['first']
                self.cpp_info.components['second'].libs = ['donottouch']
                self.cpp_info.components['second'].requires = ['first']
        """)

    uses_components = textwrap.dedent("""
        from conan import ConanFile
        class PkgUsesComponent(ConanFile):
            name = 'uses_components'
            version = '1.0'
            settings = 'os', 'compiler', 'arch', 'build_type'
            def requirements(self):
                self.requires('has_components/1.0')
            def package_info(self):
                self.cpp_info.libs = ['uses_only_first']
                self.cpp_info.requires = ['has_components::first']
        """)

    consumer = textwrap.dedent("""
        [requires]
        uses_components/1.0
        """)

    client.save({"has_components.py": has_components,
                 "uses_components.py": uses_components,
                 "consumer.txt": consumer})
    client.run("create has_components.py")
    client.run("create uses_components.py")
    client.run("install consumer.txt -g XcodeDeps")
    conandeps = client.load("conandeps.xcconfig")
    assert '#include "conan_has_components.xcconfig"' not in conandeps
    assert '#include "conan_uses_components.xcconfig"' in conandeps
    conan_uses_xcconfig = client.load("conan_uses_components_uses_components.xcconfig")
    assert '#include "conan_has_components_first.xcconfig"' in conan_uses_xcconfig
    assert '#include "conan_has_components_second.xcconfig"' not in conan_uses_xcconfig
