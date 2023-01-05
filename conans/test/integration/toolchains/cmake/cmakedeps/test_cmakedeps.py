import os
import platform
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_package_from_system():
    """
    If a node declares "system_package" property, the CMakeDeps generator will skip generating
    the -config.cmake and the other files for that node but will keep the "find_dependency" for
    the nodes depending on it. That will cause that cmake looks for the config files elsewhere
    https://github.com/conan-io/conan/issues/8919"""
    client = TestClient()
    dep2 = str(GenConanfile().with_name("dep2").with_version("1.0")
               .with_settings("os", "arch", "build_type", "compiler"))
    dep2 += """
    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "None")
        self.cpp_info.set_property("cmake_file_name", "custom_dep2")

    """
    client.save({"conanfile.py": dep2})
    client.run("create .")

    dep1 = GenConanfile().with_name("dep1").with_version("1.0").with_require("dep2/1.0")\
                         .with_settings("os", "arch", "build_type", "compiler")
    client.save({"conanfile.py": dep1})
    client.run("create .")

    consumer = GenConanfile().with_name("consumer").with_version("1.0").\
        with_require("dep1/1.0").with_generator("CMakeDeps").\
        with_settings("os", "arch", "build_type", "compiler")
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
    client.run("create . gtest/1.0@")
    client.run("create . cmake/1.0@")

    client.save({"conanfile.py": GenConanfile().with_build_requires("cmake/1.0").
                with_build_requirement("gtest/1.0", force_host_context=True)})

    client.run("export . pkg/1.0@")

    consumer = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps"
            requires = "pkg/1.0"
        """)
    client.save({"conanfile.py": consumer})
    client.run("install . -s:b os=Windows -s:h os=Linux -s:h arch=x86_64 --build=missing")
    cmake_data = client.load("pkg-release-x86_64-data.cmake")
    assert "gtest" not in cmake_data


def test_components_error():
    # https://github.com/conan-io/conan/issues/9331
    client = TestClient()

    conan_hello = textwrap.dedent("""
        import os
        from conans import ConanFile

        from conan.tools.files import save
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"

            def layout(self):
                pass

            def package_info(self):
                self.cpp_info.components["say"].includedirs = ["include"]
            """)

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@")


def test_cpp_info_component_objects():
    client = TestClient()
    conan_hello = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "arch", "build_type"
            def package_info(self):
                self.cpp_info.components["say"].objects = ["mycomponent.o"]
            """)

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@ -s arch=x86_64 -s build_type=Release")
    client.run("install hello/1.0@ -g CMakeDeps -s arch=x86_64 -s build_type=Release")
    with open(os.path.join(client.current_folder, "hello-Target-release.cmake")) as f:
        content = f.read()
        assert """set_property(TARGET hello::say
                     PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:Release>:${hello_hello_say_OBJECTS_RELEASE}>
                     $<$<CONFIG:Release>:${hello_hello_say_LIBRARIES_TARGETS}>
                     APPEND)""" in content
        # If there are componets, there is not a global cpp so this is not generated
        assert "hello_OBJECTS_RELEASE" not in content
        # But the global target is linked with the targets from the components
        assert "set_property(TARGET hello::hello PROPERTY INTERFACE_LINK_LIBRARIES " \
               "hello::say APPEND)" in content

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
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            requires = "hello/1.0"
            generators = "VirtualRunEnv", "CMakeDeps"
            def package_info(self):
                self.cpp_info.components["chat"].requires = ["hello::say"]
        """)
    test_package = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "VirtualRunEnv", "CMakeDeps"

            def test(self):
                pass
        """)

    client.save({"hello/conanfile.py": conan_hello,
                 "consumer/conanfile.py": consumer,
                 "consumer/test_package/conanfile.py": test_package})
    client.run("create hello hello/1.0@")
    client.run("create consumer consumer/1.0@")
    assert "consumer/1.0 (test package): Running test()" in client.out


def test_cmakedeps_cppinfo_complex_strings():
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent(r'''
        from conans import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.defines.append("escape=partially \"escaped\"")
                self.cpp_info.defines.append("spaces=me you")
                self.cpp_info.defines.append("foobar=bazbuz")
                self.cpp_info.defines.append("answer=42")
        ''')
    client.save({"conanfile.py": conanfile})
    client.run("export . hello/1.0@")
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
    client.run("create bar.py bar/1.0@")
    client.run("install foo.py foo/1.0@")
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
    client.run("create bar.py bar/1.0@")
    client.run("install foo.py foo/1.0@")
    assert not os.path.exists(module_file)
    assert not os.path.exists(config_file)

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'module'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py bar/1.0@")
    client.run("install foo.py foo/1.0@")
    assert os.path.exists(module_file)
    assert not os.path.exists(config_file)

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'config'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py bar/1.0@")
    client.run("install foo.py foo/1.0@")
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
    client.run("create bar.py bar/1.0@ -pr:h=default -pr:b=default")
    client.run("install foo.py foo/1.0@ -pr:h=default -pr:b=default")
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
    client.run("create bar.py bar/1.0@ -pr:h=default -pr:b=default")
    client.run("install foo.py foo/1.0@ -pr:h=default -pr:b=default")
    assert not os.path.exists(module_file)
    assert not os.path.exists(config_file)
    assert not os.path.exists(module_file_build)
    assert not os.path.exists(config_file_build)

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'module'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py bar/1.0@ -pr:h=default -pr:b=default")
    client.run("install foo.py foo/1.0@ -pr:h=default -pr:b=default")
    assert os.path.exists(module_file)
    assert not os.path.exists(config_file)
    assert os.path.exists(module_file_build)
    assert not os.path.exists(config_file_build)

    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="'config'")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py bar/1.0@ -pr:h=default -pr:b=default")
    client.run("install foo.py foo/1.0@ -pr:h=default -pr:b=default")
    assert not os.path.exists(module_file)
    assert os.path.exists(config_file)
    assert not os.path.exists(module_file_build)
    assert os.path.exists(config_file_build)

    # invalidate upstream property setting a None, will use config that's the default
    client.save({"foo.py": foo.format(set_find_mode=set_find_mode.format(find_mode="None")),
                 "bar.py": bar}, clean_first=True)
    client.run("create bar.py bar/1.0@ -pr:h=default -pr:b=default")
    client.run("install foo.py foo/1.0@ -pr:h=default -pr:b=default")
    assert not os.path.exists(module_file)
    assert os.path.exists(config_file)
    assert not os.path.exists(module_file_build)
    assert os.path.exists(config_file_build)


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
            "example/test_package/conanfile.py": GenConanfile().with_requires("example/1.0")
                                                               .with_build_requires("example/1.0")
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

    assert "example/1.0: Package '5949422937e5ea462011eb7f38efab5745e4b832' created" in c.out
    assert "example/1.0: Package '03ed74784e8b09eda4f6311a2f461897dea57a7e' created" in c.out
