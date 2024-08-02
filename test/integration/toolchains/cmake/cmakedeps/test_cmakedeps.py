import os
import platform
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_package_from_system():
    """
    If a node declares "system_package" property, the CMakeDeps generator will skip generating
    the -config.cmake and the other files for that node but will keep the "find_dependency" for
    the nodes depending on it. That will cause that cmake looks for the config files elsewhere
    https://github.com/conan-io/conan/issues/8919"""
    client = TestClient()
    dep2 = str(GenConanfile().with_name("dep2").with_version("1.0")
               .with_settings("os", "arch", "build_type"))
    dep2 += """
    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "None")
        self.cpp_info.set_property("cmake_file_name", "custom_dep2")

    """
    client.save({"conanfile.py": dep2})
    client.run("create .")

    dep1 = GenConanfile().with_name("dep1").with_version("1.0").with_require("dep2/1.0")\
                         .with_settings("os", "arch", "build_type")
    client.save({"conanfile.py": dep1})
    client.run("create .")

    consumer = GenConanfile().with_name("consumer").with_version("1.0").\
        with_require("dep1/1.0").with_generator("CMakeDeps").\
        with_settings("os", "arch", "build_type")
    client.save({"conanfile.py": consumer})
    client.run("install .")

    assert os.path.exists(os.path.join(client.current_folder, "dep1-config.cmake"))
    assert not os.path.exists(os.path.join(client.current_folder, "dep2-config.cmake"))
    assert not os.path.exists(os.path.join(client.current_folder, "custom_dep2-config.cmake"))
    host_arch = client.get_default_host_profile().settings['arch']
    dep1_contents = client.load(f"dep1-release-{host_arch}-data.cmake")
    assert 'list(APPEND dep1_FIND_DEPENDENCY_NAMES custom_dep2)' in dep1_contents
    assert 'set(custom_dep2_FIND_MODE "")' in dep1_contents


def test_test_package():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=gtest --version=1.0")
    client.run("create . --name=cmake --version=1.0")

    client.save({"conanfile.py": GenConanfile().with_tool_requires("cmake/1.0").
                with_test_requires("gtest/1.0")})

    client.run("export . --name=pkg --version=1.0")

    consumer = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps"
            requires = "pkg/1.0"
        """)
    client.save({"conanfile.py": consumer})
    client.run("install . -s:b os=Windows -s:h os=Linux -s:h compiler=gcc -s:h compiler.version=7 "
               "-s:h compiler.libcxx=libstdc++11 -s:h arch=x86_64 --build=missing")
    cmake_data = client.load("pkg-release-x86_64-data.cmake")
    assert "gtest" not in cmake_data


def test_components_error():
    # https://github.com/conan-io/conan/issues/9331
    client = TestClient()

    conan_hello = textwrap.dedent("""
        import os
        from conan import ConanFile

        from conan.tools.files import save
        class Pkg(ConanFile):
            settings = "os"

            def layout(self):
                pass

            def package_info(self):
                self.cpp_info.components["say"].includedirs = ["include"]
            """)

    client.save({"conanfile.py": conan_hello})
    client.run("create . --name=hello --version=1.0")


def test_cpp_info_component_objects():
    client = TestClient()
    conan_hello = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "arch", "build_type"
            def package_info(self):
                self.cpp_info.components["say"].objects = ["mycomponent.o"]
            """)

    client.save({"conanfile.py": conan_hello})
    client.run("create . --name=hello --version=1.0 -s arch=x86_64 -s build_type=Release")
    client.run("install --requires=hello/1.0@ -g CMakeDeps -s arch=x86_64 -s build_type=Release")
    with open(os.path.join(client.current_folder, "hello-Target-release.cmake")) as f:
        content = f.read()
        assert """set_property(TARGET hello::say
                     APPEND PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:Release>:${hello_hello_say_OBJECTS_RELEASE}>
                     $<$<CONFIG:Release>:${hello_hello_say_LIBRARIES_TARGETS}>
                     )""" in content
        # If there are componets, there is not a global cpp so this is not generated
        assert "hello_OBJECTS_RELEASE" not in content
        # But the global target is linked with the targets from the components
        assert "set_property(TARGET hello::hello APPEND PROPERTY INTERFACE_LINK_LIBRARIES " \
               "hello::say)" in content

    with open(os.path.join(client.current_folder, "hello-release-x86_64-data.cmake")) as f:
        content = f.read()
        # https://github.com/conan-io/conan/issues/11862
        # Global variables
        assert 'set(hello_OBJECTS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/mycomponent.o")' \
               in content
        # But component variables
        assert 'set(hello_hello_say_OBJECTS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/' \
               'mycomponent.o")' in content


def test_cpp_info_component_error_aggregate():
    # https://github.com/conan-io/conan/issues/10176
    # This test was consistently failing because "VirtualRunEnv" was not doing a "copy()"
    # of cpp_info before calling "aggregate_components()", and it was destructive, removing
    # components data
    client = TestClient()
    conan_hello = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.cpp_info.components["say"].includedirs = ["include"]
            """)
    consumer = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            requires = "hello/1.0"
            generators = "VirtualRunEnv", "CMakeDeps"
            def package_info(self):
                self.cpp_info.components["chat"].requires = ["hello::say"]
        """)
    test_package = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "VirtualRunEnv", "CMakeDeps"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def test(self):
                pass
        """)

    client.save({"hello/conanfile.py": conan_hello,
                 "consumer/conanfile.py": consumer,
                 "consumer/test_package/conanfile.py": test_package})
    client.run("create hello --name=hello --version=1.0")
    client.run("create consumer --name=consumer --version=1.0")
    assert "consumer/1.0 (test package): Running test()" in client.out


def test_cmakedeps_cppinfo_complex_strings():
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.defines.append("escape=partially \"escaped\"")
                self.cpp_info.defines.append("spaces=me you")
                self.cpp_info.defines.append("foobar=bazbuz")
                self.cpp_info.defines.append("answer=42")
        ''')
    client.save({"conanfile.py": conanfile})
    client.run("export . --name=hello --version=1.0")
    client.save({"conanfile.txt": "[requires]\nhello/1.0\n"}, clean_first=True)
    client.run("install . --build=missing -g CMakeDeps")
    arch = client.get_default_host_profile().settings['arch']
    deps = client.load(f"hello-release-{arch}-data.cmake")
    assert r"escape=partially \"escaped\"" in deps
    assert r"spaces=me you" in deps
    assert r"foobar=bazbuz" in deps
    assert r"answer=42" in deps


def test_dependency_props_from_consumer():
    client = TestClient(path_with_spaces=False)
    bar = textwrap.dedent(r'''
        from conan import ConanFile
        class FooConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.set_property("cmake_find_mode", "both")
                self.cpp_info.components["component1"].requires = []
        ''')

    foo = textwrap.dedent(r'''
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps, cmake_layout
        class FooConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "bar/1.0"
            def layout(self):
                cmake_layout(self)
            def generate(self):
                deps = CMakeDeps(self)
                {set_find_mode}
                deps.set_property("bar", "cmake_file_name", "custom_bar_file_name")
                deps.set_property("bar", "cmake_module_file_name", "custom_bar_module_file_name")
                deps.set_property("bar", "cmake_target_name", "custom_bar_target_name")
                deps.set_property("bar", "cmake_module_target_name", "custom_bar_module_target_name")
                deps.set_property("bar::component1", "cmake_target_name", "custom_bar_component_target_name")
                deps.generate()
        ''')

    set_find_mode = """
        deps.set_property("bar", "cmake_find_mode", {find_mode})
    """

    client.save({"foo.py": foo.format(set_find_mode=""), "bar.py": bar}, clean_first=True)

    if platform.system() != "Windows":
        gen_folder = os.path.join(client.current_folder, "build", "Release", "generators")
    else:
        gen_folder = os.path.join(client.current_folder, "build", "generators")

    module_file = os.path.join(gen_folder, "module-custom_bar_module_file_nameTargets.cmake")
    components_module = os.path.join(gen_folder, "custom_bar_file_name-Target-release.cmake")
    config_file = os.path.join(gen_folder, "custom_bar_file_nameTargets.cmake")

    # uses cmake_find_mode set in bar: both
    client.run("create bar.py --name=bar --version=1.0")
    client.run("install foo.py")
    assert os.path.exists(module_file)
    assert os.path.exists(config_file)
    module_content = client.load(module_file)
    assert "add_library(custom_bar_module_target_name INTERFACE IMPORTED)" in module_content
    config_content = client.load(config_file)
    assert "add_library(custom_bar_target_name INTERFACE IMPORTED)" in config_content
    components_module_content = client.load(components_module)
    assert "add_library(bar_custom_bar_component_target_name_DEPS_TARGET INTERFACE IMPORTED)" in components_module_content

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'none'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py --name=bar --version=1.0")
    client.run("install foo.py")
    assert not os.path.exists(module_file)
    assert not os.path.exists(config_file)

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'module'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py --name=bar --version=1.0")
    client.run("install foo.py")
    assert os.path.exists(module_file)
    assert not os.path.exists(config_file)

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'config'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py --name=bar --version=1.0")
    client.run("install foo.py")
    assert not os.path.exists(module_file)
    assert os.path.exists(config_file)


def test_props_from_consumer_build_context_activated():
    client = TestClient(path_with_spaces=False)
    bar = textwrap.dedent(r'''
        from conan import ConanFile
        class FooConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.set_property("cmake_find_mode", "both")
                self.cpp_info.components["component1"].requires = []
        ''')

    foo = textwrap.dedent(r'''
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps, cmake_layout
        class FooConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "bar/1.0"
            tool_requires = "bar/1.0"
            def layout(self):
                cmake_layout(self)
            def generate(self):
                deps = CMakeDeps(self)
                deps.build_context_activated = ["bar"]
                deps.build_context_suffix = {{"bar": "_BUILD"}}
                {set_find_mode}

                deps.set_property("bar", "cmake_file_name", "custom_bar_file_name")
                deps.set_property("bar", "cmake_module_file_name", "custom_bar_module_file_name")
                deps.set_property("bar", "cmake_target_name", "custom_bar_target_name")
                deps.set_property("bar", "cmake_module_target_name", "custom_bar_module_target_name")
                deps.set_property("bar::component1", "cmake_target_name", "custom_bar_component_target_name")

                deps.set_property("bar", "cmake_file_name", "custom_bar_build_file_name", build_context=True)
                deps.set_property("bar", "cmake_module_file_name", "custom_bar_build_module_file_name", build_context=True)
                deps.set_property("bar", "cmake_target_name", "custom_bar_build_target_name", build_context=True)
                deps.set_property("bar", "cmake_module_target_name", "custom_bar_build_module_target_name", build_context=True)
                deps.set_property("bar::component1", "cmake_target_name", "custom_bar_build_component_target_name", build_context=True)

                deps.generate()
        ''')

    set_find_mode = """
        deps.set_property("bar", "cmake_find_mode", {find_mode})
        deps.set_property("bar", "cmake_find_mode", {find_mode}, build_context=True)
    """

    client.save({"foo.py": foo.format(set_find_mode=""), "bar.py": bar}, clean_first=True)

    if platform.system() != "Windows":
        gen_folder = os.path.join(client.current_folder, "build", "Release", "generators")
    else:
        gen_folder = os.path.join(client.current_folder, "build", "generators")

    module_file = os.path.join(gen_folder, "module-custom_bar_module_file_nameTargets.cmake")
    components_module = os.path.join(gen_folder, "custom_bar_file_name-Target-release.cmake")
    config_file = os.path.join(gen_folder, "custom_bar_file_nameTargets.cmake")

    module_file_build = os.path.join(gen_folder,
                                     "module-custom_bar_build_module_file_name_BUILDTargets.cmake")
    components_module_build = os.path.join(gen_folder,
                                           "custom_bar_build_file_name_BUILD-Target-release.cmake")
    config_file_build = os.path.join(gen_folder, "custom_bar_build_file_name_BUILDTargets.cmake")

    # uses cmake_find_mode set in bar: both
    client.run("create bar.py --name=bar --version=1.0 -pr:h=default -pr:b=default")
    client.run("install foo.py --name=foo --version=1.0 -pr:h=default -pr:b=default")
    assert os.path.exists(module_file)
    assert os.path.exists(config_file)
    assert os.path.exists(module_file_build)
    assert os.path.exists(config_file_build)

    module_content = client.load(module_file)
    assert "add_library(custom_bar_module_target_name INTERFACE IMPORTED)" in module_content
    config_content = client.load(config_file)
    assert "add_library(custom_bar_target_name INTERFACE IMPORTED)" in config_content

    module_content_build = client.load(module_file_build)
    assert "add_library(custom_bar_build_module_target_name INTERFACE IMPORTED)" in module_content_build
    config_content_build = client.load(config_file_build)
    assert "add_library(custom_bar_build_target_name INTERFACE IMPORTED)" in config_content_build

    components_module_content = client.load(components_module)
    assert "add_library(bar_custom_bar_component_target_name_DEPS_TARGET INTERFACE IMPORTED)" in components_module_content

    components_module_content_build = client.load(components_module_build)
    assert "add_library(bar_BUILD_custom_bar_build_component_target_name_DEPS_TARGET INTERFACE IMPORTED)" in components_module_content_build

    client.save(
        {"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'none'")), "bar.py": bar},
        clean_first=True)
    client.run("create bar.py --name=bar --version=1.0 -pr:h=default -pr:b=default")
    client.run("install foo.py --name=foo --version=1.0 -pr:h=default -pr:b=default")
    assert not os.path.exists(module_file)
    assert not os.path.exists(config_file)
    assert not os.path.exists(module_file_build)
    assert not os.path.exists(config_file_build)

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'module'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py --name=bar --version=1.0 -pr:h=default -pr:b=default")
    client.run("install foo.py --name=foo --version=1.0 -pr:h=default -pr:b=default")
    assert os.path.exists(module_file)
    assert not os.path.exists(config_file)
    assert os.path.exists(module_file_build)
    assert not os.path.exists(config_file_build)

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'config'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py --name=bar --version=1.0 -pr:h=default -pr:b=default")
    client.run("install foo.py --name=foo --version=1.0 -pr:h=default -pr:b=default")
    assert not os.path.exists(module_file)
    assert os.path.exists(config_file)
    assert not os.path.exists(module_file_build)
    assert os.path.exists(config_file_build)

    # invalidate upstream property setting a None, will use config that's the default
    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="None")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py --name=bar --version=1.0 -pr:h=default -pr:b=default")
    client.run("install foo.py --name=foo --version=1.0 -pr:h=default -pr:b=default")
    assert not os.path.exists(module_file)
    assert os.path.exists(config_file)
    assert not os.path.exists(module_file_build)
    assert os.path.exists(config_file_build)


def test_skip_transitive_components():
    """ when a transitive depenency is skipped, because its binary is not necessary
    (shared->static), the ``components[].requires`` clause pointing to that skipped dependency
    was failing with KeyError, as the dependency info was not there
    """
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            package_type = "shared-library"
            requires = "dep/0.1"
            def package_info(self):
                self.cpp_info.components["mycomp"].requires = ["dep::dep"]
        """)

    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1").with_package_type("static-library"),
            "pkg/conanfile.py": pkg,
            "consumer/conanfile.py": GenConanfile().with_settings("build_type")
                                                   .with_requires("pkg/0.1")})
    c.run("create dep")
    c.run("create pkg")
    c.run("install consumer -g CMakeDeps -v")
    c.assert_listed_binary({"dep": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Skip")})
    # This used to error, as CMakeDeps was raising a KeyError
    assert "'CMakeDeps' calling 'generate()'" in c.out


def test_error_missing_config_build_context():
    """
    CMakeDeps was failing, not generating the zlib-config.cmake in the
    build context, for a test_package that both requires(example/1.0) and
    tool_requires(example/1.0), which depends on zlib
    # https://github.com/conan-io/conan/issues/12664
    """
    c = TestClient()
    example = textwrap.dedent("""
        import os
        from conan import ConanFile
        class Example(ConanFile):
            name = "example"
            version = "1.0"
            requires = "game/1.0"
            generators = "CMakeDeps"
            settings = "build_type"
            def build(self):
                assert os.path.exists("math-config.cmake")
                assert os.path.exists("engine-config.cmake")
                assert os.path.exists("game-config.cmake")
            """)
    c.save({"math/conanfile.py": GenConanfile("math", "1.0").with_settings("build_type"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_settings("build_type")
                                                                .with_require("math/1.0"),
            "game/conanfile.py": GenConanfile("game", "1.0").with_settings("build_type")
                                                            .with_requires("engine/1.0"),
            "example/conanfile.py": example,
            # The example test_package contains already requires(self.tested_reference_str)
            "example/test_package/conanfile.py": GenConanfile().with_build_requires("example/1.0")
                                                               .with_test("pass")})
    c.run("create math")
    c.run("create engine")
    c.run("create game")
    # This used to crash because of the assert inside the build() method
    c.run("create example -pr:b=default -pr:h=default")
    # Now make sure we can actually build with build!=host context
    # The debug binaries are missing, so adding --build=missing
    c.run("create example -pr:b=default -pr:h=default -s:h build_type=Debug --build=missing "
          "--build=example")

    # listed as both requires and build_requires
    c.assert_listed_require({"example/1.0": "Cache"})
    c.assert_listed_require({"example/1.0": "Cache"}, build=True)


def test_using_package_module():
    """
    This crashed, because the profile "build" didn't have "build_type"
    https://github.com/conan-io/conan/issues/13209
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("tool", "0.1")})
    c.run("create .")

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            tool_requires = "tool/0.1"

            def generate(self):
                deps = CMakeDeps(self)
                deps.build_context_activated = ["tool"]
                deps.build_context_build_modules = ["tool"]
                deps.generate()
        """)
    c.save({"conanfile.py": consumer,
            "profile_build": "[settings]\nos=Windows"}, clean_first=True)
    c.run("create . -pr:b=profile_build")
    # it doesn't crash anymore, it used to crash
    assert "pkg/0.1: Created package" in c.out


def test_system_libs_transitivity():
    """
    https://github.com/conan-io/conan/issues/13358
    """
    c = TestClient()
    system = textwrap.dedent("""\
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "system"
            def package_info(self):
                self.cpp_info.system_libs = ["m"]
                self.cpp_info.frameworks = ["CoreFoundation"]
            """)
    header = textwrap.dedent("""
        from conan import ConanFile
        class Header(ConanFile):
            name = "header"
            version = "0.1"
            package_type = "header-library"
            requires = "dep/system"
            def package_info(self):
                self.cpp_info.system_libs = ["dl"]
                self.cpp_info.frameworks = ["CoreDriver"]
            """)
    app = textwrap.dedent("""\
        from conan import ConanFile
        class App(ConanFile):
            requires = "header/0.1"
            settings = "build_type"
            generators = "CMakeDeps"
        """)
    c.save({"dep/conanfile.py": system,
            "header/conanfile.py": header,
            "app/conanfile.py": app})
    c.run("create dep")
    c.run("create header")
    c.run("install app")
    dep = c.load("app/dep-release-data.cmake")
    assert "set(dep_SYSTEM_LIBS_RELEASE m)" in dep
    assert "set(dep_FRAMEWORKS_RELEASE CoreFoundation)" in dep
    app = c.load("app/header-release-data.cmake")
    assert "set(header_SYSTEM_LIBS_RELEASE dl)" in app
    assert "set(header_FRAMEWORKS_RELEASE CoreDriver)" in app


class TestCMakeVersionConfigCompat:
    """
    https://github.com/conan-io/conan/issues/13809
    """
    def test_cmake_version_config_compatibility(self):
        c = TestClient()
        dep = textwrap.dedent("""\
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "dep"
                version = "0.1"
                def package_info(self):
                    self.cpp_info.set_property("cmake_config_version_compat", "AnyNewerVersion")
                """)

        c.save({"conanfile.py": dep})
        c.run("create .")
        c.run("install --requires=dep/0.1 -g CMakeDeps")
        dep = c.load("dep-config-version.cmake")
        expected = textwrap.dedent("""\
            if(PACKAGE_VERSION VERSION_LESS PACKAGE_FIND_VERSION)
                set(PACKAGE_VERSION_COMPATIBLE FALSE)
            else()
                set(PACKAGE_VERSION_COMPATIBLE TRUE)

                if(PACKAGE_FIND_VERSION STREQUAL PACKAGE_VERSION)
                    set(PACKAGE_VERSION_EXACT TRUE)
                endif()
            endif()""")
        assert expected in dep

    def test_cmake_version_config_compatibility_error(self):
        c = TestClient()
        dep = textwrap.dedent("""\
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "dep"
                version = "0.1"
                def package_info(self):
                    self.cpp_info.set_property("cmake_config_version_compat", "Unknown")
                """)

        c.save({"conanfile.py": dep})
        c.run("create .")
        c.run("install --requires=dep/0.1 -g CMakeDeps", assert_error=True)
        assert "Unknown cmake_config_version_compat=Unknown in dep/0.1" in c.out

    def test_cmake_version_config_compatibility_consumer(self):
        c = TestClient()
        app = textwrap.dedent("""\
            from conan import ConanFile
            from conan.tools.cmake import CMakeDeps
            class Pkg(ConanFile):
                settings = "build_type"
                requires = "dep/0.1"
                def generate(self):
                    deps = CMakeDeps(self)
                    deps.set_property("dep", "cmake_config_version_compat", "AnyNewerVersion")
                    deps.generate()
                """)

        c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                "app/conanfile.py": app})
        c.run("create dep")
        c.run("install app")
        dep = c.load("app/dep-config-version.cmake")
        expected = textwrap.dedent("""\
            if(PACKAGE_VERSION VERSION_LESS PACKAGE_FIND_VERSION)
                set(PACKAGE_VERSION_COMPATIBLE FALSE)
            else()
                set(PACKAGE_VERSION_COMPATIBLE TRUE)

                if(PACKAGE_FIND_VERSION STREQUAL PACKAGE_VERSION)
                    set(PACKAGE_VERSION_EXACT TRUE)
                endif()
            endif()""")
        assert expected in dep


class TestSystemPackageVersion:
    def test_component_version(self):
        c = TestClient()
        dep = textwrap.dedent("""\
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "dep"
                version = "system"
                def package_info(self):
                    self.cpp_info.set_property("system_package_version", "1.0")
                    self.cpp_info.components["mycomp"].set_property("component_version", "2.3")
                """)

        c.save({"conanfile.py": dep})
        c.run("create .")
        c.run("install --requires=dep/system -g CMakeDeps -g PkgConfigDeps")
        dep = c.load("dep-config-version.cmake")
        assert 'set(PACKAGE_VERSION "1.0")' in dep
        dep = c.load("dep.pc")
        assert 'Version: 1.0' in dep
        dep = c.load("dep-mycomp.pc")
        assert 'Version: 2.3' in dep

    def test_component_version_consumer(self):
        c = TestClient()
        app = textwrap.dedent("""\
            from conan import ConanFile
            from conan.tools.cmake import CMakeDeps
            class Pkg(ConanFile):
                settings = "build_type"
                requires = "dep/system"
                def generate(self):
                    deps = CMakeDeps(self)
                    deps.set_property("dep", "system_package_version", "1.0")
                    deps.generate()
                """)

        c.save({"dep/conanfile.py": GenConanfile("dep", "system"),
                "app/conanfile.py": app})
        c.run("create dep")
        c.run("install app")
        dep = c.load("app/dep-config-version.cmake")
        assert 'set(PACKAGE_VERSION "1.0")' in dep


def test_cmakedeps_set_property_overrides():
    c = TestClient()
    app = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps
        class Pkg(ConanFile):
            settings = "build_type"
            requires = "dep/0.1", "other/0.1"
            def generate(self):
                deps = CMakeDeps(self)
                # Need the absolute path inside package
                dep = self.dependencies["dep"].package_folder
                deps.set_property("dep", "cmake_build_modules", [os.path.join(dep, "my_module1")])
                deps.set_property("dep", "nosoname", True)
                deps.set_property("other::mycomp1", "nosoname", True)
                deps.generate()
            """)

    pkg_info = {"components": {"mycomp1": {"libs": ["mylib"]}}}
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1").with_package_type("shared-library"),
            "other/conanfile.py": GenConanfile("other", "0.1").with_package_type("shared-library")
                                                              .with_package_info(pkg_info, {}),
            "app/conanfile.py": app})
    c.run("create dep")
    c.run("create other")
    c.run("install app")
    dep = c.load("app/dep-release-data.cmake")
    assert 'set(dep_BUILD_MODULES_PATHS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/my_module1")' in dep
    assert 'set(dep_NO_SONAME_MODE_RELEASE TRUE)' in dep
    other = c.load("app/other-release-data.cmake")
    assert 'set(other_other_mycomp1_NO_SONAME_MODE_RELEASE TRUE)' in other


def test_cmakedeps_set_legacy_variable_name():
    client = TestClient()
    base_conanfile = str(GenConanfile("dep", "1.0"))
    conanfile = base_conanfile + """
    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "CMakeFileName")
    """
    client.save({"dep/conanfile.py": conanfile})
    client.run("create dep")
    client.run("install --requires=dep/1.0 -g CMakeDeps")

    # Check that all the CMake variables are generated with the file_name
    dep_config = client.load("CMakeFileNameConfig.cmake")
    cmake_variables = ["VERSION_STRING", "INCLUDE_DIRS", "INCLUDE_DIR", "LIBRARIES", "DEFINITIONS"]
    for variable in cmake_variables:
        assert f"CMakeFileName_{variable}" in dep_config

    conanfile = base_conanfile + """
    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "NewCMakeFileName")
        self.cpp_info.set_property("cmake_additional_variables_prefixes", ["PREFIX", "prefix", "PREFIX"])
    """
    client.save({"dep/conanfile.py": conanfile})
    client.run("create dep")
    client.run("install --requires=dep/1.0 -g CMakeDeps")

    # Check that all the CMake variables are generated with the file_name and both prefixes
    dep_config = client.load("NewCMakeFileNameConfig.cmake")
    for variable in cmake_variables:
        assert f"NewCMakeFileName_{variable}" in dep_config
        assert f"PREFIX_{variable}" in dep_config
        assert f"prefix_{variable}" in dep_config
    # Check that variables are not duplicated
    assert dep_config.count("PREFIX_VERSION") == 1


def test_different_versions():
    # https://github.com/conan-io/conan/issues/16274
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep")})
    c.run("create dep --version 1.2")
    c.run("create dep --version 2.3")
    c.run("install --requires=dep/1.2 -g CMakeDeps")
    config = c.load("dep-config.cmake")
    assert 'set(dep_VERSION_STRING "1.2")' in config
    c.run("install --requires=dep/2.3 -g CMakeDeps")
    config = c.load("dep-config.cmake")
    assert 'set(dep_VERSION_STRING "2.3")' in config


def test_using_deployer_folder():
    """
    Related to: https://github.com/conan-io/conan/issues/16543

    CMakeDeps was failing if --deployer-folder was used. The error looked like:

    conans.errors.ConanException: Error in generator 'CMakeDeps': error generating context for 'dep/1.0': mydeploy/direct_deploy/dep/include is not absolute
    """
    c = TestClient()
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=apple-clang
    compiler.cppstd=gnu17
    compiler.libcxx=libc++
    compiler.version=15
    os=Macos
    """)
    c.save({
        "profile": profile,
        "dep/conanfile.py": GenConanfile("dep")})
    c.run("create dep --version 1.0")
    c.run("install --requires=dep/1.0 -pr profile --deployer=direct_deploy "
          "--deployer-folder=mydeploy -g CMakeDeps")
    content = c.load("dep-release-x86_64-data.cmake")
    assert ('set(dep_PACKAGE_FOLDER_RELEASE "${CMAKE_CURRENT_LIST_DIR}/mydeploy/direct_deploy/dep")'
            in content)
