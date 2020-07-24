import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference
from conans.test.utils.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


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

    def basic_test(self):
        client = TestClient()
        self._create_greetings(client)
        self._create_world(client)
        client.run("install world/0.0.1@ -g pkg_config")
        self.assertNotIn("Requires:", client.load(os.path.join(client.current_folder, "hello.pc")))
        self.assertNotIn("Requires:", client.load(os.path.join(client.current_folder, "bye.pc")))
        self.assertIn("Requires: bye hello",
                      client.load(os.path.join(client.current_folder, "greetings.pc")))

    def pkg_config_general_test(self):
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
        world_pc = client.load(os.path.join(client.current_folder, "World.pc"))
        worldall_pc = client.load(os.path.join(client.current_folder, "Worldall.pc"))
        helloworld_pc = client.load(os.path.join(client.current_folder, "Helloworld.pc"))
        self.assertIn("Requires: Bye Helloworld", worldall_pc)
        self.assertIn("Requires: Hello", helloworld_pc)
        self.assertIn("Requires: Helloworld Worldall", world_pc)  #TODO reverse order?

    def pkg_config_components_test(self):
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
        world_pc = client.load(os.path.join(client.current_folder, "world.pc"))
        worldall_pc = client.load(os.path.join(client.current_folder, "worldall.pc"))
        helloworld_pc = client.load(os.path.join(client.current_folder, "helloworld.pc"))
        self.assertIn("Requires: helloworld bye", worldall_pc)
        self.assertIn("Requires: hello", helloworld_pc)
        self.assertIn("Requires: helloworld worldall", world_pc)  #TODO: reverse order?

    def recipe_with_components_requiring_recipe_without_components_test(self):
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
        greetings_pc = client.load(os.path.join(client.current_folder, "greetings.pc"))
        self.assertNotIn("Requires:", greetings_pc)
        self.assertIn("Libs: -L${libdir} -lhello  -lbye", greetings_pc)
        world_pc = client.load(os.path.join(client.current_folder, "world.pc"))
        self.assertIn("Requires: helloworld worldall", world_pc)
        self.assertNotIn("Libs:", world_pc)
        worldall_pc = client.load(os.path.join(client.current_folder, "worldall.pc"))
        self.assertIn("Requires: helloworld greetings", worldall_pc)
        self.assertIn("Libs: -L${libdir} -lworldall", worldall_pc)
        helloworld_pc = client.load(os.path.join(client.current_folder, "helloworld.pc"))
        self.assertIn("Requires: greetings", helloworld_pc)
        self.assertIn("Libs: -L${libdir} -lhelloworld", helloworld_pc)

    def same_names_test(self):
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
        self.assertNotIn("Requires:", client.load(os.path.join(client.current_folder, "hello.pc")))

    def component_not_found_same_name_as_pkg_require_test(self):
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

