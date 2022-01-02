import os
import textwrap
import unittest

import pytest

from conans.client.tools import PkgConfig, environment_append
from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.tool_pkg_config
class PkgConfigGeneratorWithComponentsTest(unittest.TestCase):

    @staticmethod
    def _create_greetings(client, custom_names=False, components=True):
        conanfile_greetings = textwrap.dedent("""
            from conans import ConanFile, CMake

            class GreetingsConan(ConanFile):
                name = "greetings"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"

                def package_info(self):
                %s
            """)
        if components:
            info = textwrap.dedent("""
                        self.cpp_info.components["hello"].libs = ["hello"]
                        self.cpp_info.components["bye"].libs = ["bye"]
                        """)
            if custom_names:
                info += textwrap.dedent("""
                        self.cpp_info.names["pkg_config"] = "Greetings"
                        self.cpp_info.components["hello"].names["pkg_config"] = "Hello"
                        self.cpp_info.components["bye"].names["pkg_config"] = "Bye"
                        """)
        else:
            info = textwrap.dedent("""
                        self.cpp_info.libs = ["hello", "bye"]
                        """)
        wrapper = textwrap.TextWrapper(width=81, initial_indent="   ", subsequent_indent="        ")
        conanfile_greetings = conanfile_greetings % wrapper.fill(info)
        client.save({"conanfile.py": conanfile_greetings})
        client.run("create .")

    @staticmethod
    def _create_world(client, conanfile=None):
        _conanfile_world = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                requires = "greetings/0.0.1"

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].requires = ["helloworld",
                                                                     "greetings::greetings"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
            """)
        client.save({"conanfile.py": conanfile or _conanfile_world})
        client.run("create .")

    @staticmethod
    def _get_libs_from_pkg_config(library, folder):
        with environment_append({"PKG_CONFIG_PATH": folder}):
            pconfig = PkgConfig(library)
            libs = pconfig.libs_only_l
        return libs

    def test_basic(self):
        client = TestClient()
        self._create_greetings(client)
        self._create_world(client)
        client.run("install world/0.0.1@ -g pkg_config")
        self.assertNotIn("Requires:", client.load("hello.pc"))
        self.assertNotIn("Requires:", client.load("bye.pc"))
        self.assertIn("Requires: bye hello", client.load("greetings.pc"))
        for f in ["hello.pc", "bye.pc", "greetings.pc", "world.pc", "helloworld.pc", "worldall.pc"]:
            self.assertIn("Version: 0.0.1", client.load(f))
        libs = self._get_libs_from_pkg_config("greetings", client.current_folder)
        self.assertListEqual(["-lbye", "-lhello"], libs)

    def test_pkg_config_general(self):
        client = TestClient()
        self._create_greetings(client, custom_names=True)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                requires = "greetings/0.0.1"

                def package_info(self):
                    self.cpp_info.names["pkg_config"] = "World"
                    self.cpp_info.components["helloworld"].names["pkg_config"] = "Helloworld"
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["Helloworld"]
                    self.cpp_info.components["worldall"].names["pkg_config"] = "Worldall"
                    self.cpp_info.components["worldall"].requires = ["greetings::bye", "helloworld"]
                    self.cpp_info.components["worldall"].libs = ["Worldall"]
        """)
        self._create_world(client, conanfile=conanfile)
        client.run("install world/0.0.1@ -g pkg_config")
        libs = self._get_libs_from_pkg_config("Worldall", client.current_folder)
        self.assertListEqual(["-lWorldall", "-lbye", "-lHelloworld", "-lhello"], libs)
        libs = self._get_libs_from_pkg_config("Helloworld", client.current_folder)
        self.assertListEqual(["-lHelloworld", "-lhello"], libs)
        libs = self._get_libs_from_pkg_config("World", client.current_folder)
        self.assertListEqual(["-lWorldall", "-lbye", "-lHelloworld", "-lhello"], libs)
        for f in ["Hello.pc", "Bye.pc", "Greetings.pc", "World.pc", "Helloworld.pc", "Worldall.pc"]:
            self.assertIn("Version: 0.0.1", client.load(f))

    def test_pkg_config_components(self):
        client = TestClient()
        self._create_greetings(client)
        conanfile2 = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                requires = "greetings/0.0.1"

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].requires = ["helloworld", "greetings::bye"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
        """)
        self._create_world(client, conanfile=conanfile2)
        client.run("install world/0.0.1@ -g pkg_config")
        libs = self._get_libs_from_pkg_config("helloworld", client.current_folder)
        self.assertListEqual(["-lhelloworld", "-lhello"], libs)
        libs = self._get_libs_from_pkg_config("worldall", client.current_folder)
        self.assertListEqual(["-lworldall", "-lhelloworld", "-lhello", "-lbye"], libs)
        world_pc = client.load("world.pc")
        self.assertIn("Requires: helloworld worldall", world_pc)
        libs = self._get_libs_from_pkg_config("world", client.current_folder)
        self.assertListEqual(["-lworldall", "-lhelloworld", "-lhello", "-lbye"], libs)
        for f in ["hello.pc", "bye.pc", "greetings.pc", "world.pc", "helloworld.pc", "worldall.pc"]:
            self.assertIn("Version: 0.0.1", client.load(f))

    def test_recipe_with_components_requiring_recipe_without_components(self):
        client = TestClient()
        self._create_greetings(client, components=False)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                requires = "greetings/0.0.1"

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::greetings"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].requires = ["helloworld",
                                                                     "greetings::greetings"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
            """)
        self._create_world(client, conanfile=conanfile)
        client.run("install world/0.0.1@ -g pkg_config")
        self.assertFalse(os.path.isfile(os.path.join(client.current_folder, "hello.pc")))
        self.assertFalse(os.path.isfile(os.path.join(client.current_folder, "bye.pc")))
        greetings_pc = client.load("greetings.pc")
        self.assertNotIn("Requires:", greetings_pc)
        libs = self._get_libs_from_pkg_config("greetings", client.current_folder)
        self.assertListEqual(["-lhello", "-lbye"], libs)
        libs = self._get_libs_from_pkg_config("world", client.current_folder)
        self.assertListEqual(["-lworldall", "-lhelloworld", "-lhello", "-lbye"], libs)
        libs = self._get_libs_from_pkg_config("helloworld", client.current_folder)
        self.assertListEqual(["-lhelloworld", "-lhello", "-lbye"], libs)
        libs = self._get_libs_from_pkg_config("worldall", client.current_folder)
        self.assertListEqual(["-lworldall", "-lhelloworld", "-lhello", "-lbye"], libs)
        for f in ["greetings.pc", "world.pc", "helloworld.pc", "worldall.pc"]:
            self.assertIn("Version: 0.0.1", client.load(f))

    def test_same_names(self):
        client = TestClient()
        conanfile_greetings = textwrap.dedent("""
            from conans import ConanFile, CMake

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"

                def package_info(self):
                    self.cpp_info.components["global"].name = "hello"
                    self.cpp_info.components["global"].libs = ["hello"]
            """)
        client.save({"conanfile.py": conanfile_greetings})
        client.run("create .")
        client.run("install hello/0.0.1@ -g pkg_config")
        self.assertNotIn("Requires:", client.load("hello.pc"))
        self.assertIn("Version: 0.0.1", client.load("hello.pc"))

    def test_component_not_found_same_name_as_pkg_require(self):
        zlib = GenConanfile("zlib", "0.1").with_setting("build_type")\
            .with_generator("pkg_config")
        mypkg = GenConanfile("mypkg", "0.1").with_setting("build_type")\
            .with_generator("pkg_config")
        final = GenConanfile("final", "0.1").with_setting("build_type")\
            .with_generator("pkg_config")\
            .with_require(ConanFileReference("zlib", "0.1", None, None))\
            .with_require(ConanFileReference("mypkg", "0.1", None, None))\
            .with_package_info(cpp_info={"components": {"cmp": {"requires": ["mypkg::zlib",
                                                                             "zlib::zlib"]}}},
                               env_info={})
        consumer = GenConanfile("consumer", "0.1").with_setting("build_type")\
            .with_generator("pkg_config")\
            .with_requirement(ConanFileReference("final", "0.1", None, None))
        client = TestClient()
        client.save({"zlib.py": zlib, "mypkg.py": mypkg, "final.py": final, "consumer.py": consumer})
        client.run("create zlib.py")
        client.run("create mypkg.py")
        client.run("create final.py")
        client.run("install consumer.py", assert_error=True)
        self.assertIn("Component 'mypkg::zlib' not found in 'mypkg' package requirement", client.out)
