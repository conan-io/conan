import textwrap
import unittest

from conans.test.utils.tools import TestClient


class MarkDownGeneratorTest(unittest.TestCase):
    def test_cmake_find_filename(self):
        conanfile = textwrap.dedent("""
                    from conans import ConanFile

                    class HelloConan(ConanFile):
                        def package_info(self):
                            self.cpp_info.set_property("cmake_file_name", "FooBar")
                            self.cpp_info.set_property("cmake_target_name", "foobar")
                            self.cpp_info.set_property("pkg_config_name", "foobar_cfg")
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertIn("find_package(FooBar)", content)
        self.assertIn("target_link_libraries(${PROJECT_NAME} foobar)", content)

    def test_cmake_find_filename_with_namespace(self):
        conanfile = textwrap.dedent("""
                    from conans import ConanFile

                    class HelloConan(ConanFile):
                        def package_info(self):
                            self.cpp_info.set_property("cmake_file_name", "FooBar")
                            self.cpp_info.set_property("cmake_target_name", "foobar::foobar")
                            self.cpp_info.set_property("pkg_config_name", "foobar_cfg")
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertIn("find_package(FooBar)", content)
        self.assertIn("target_link_libraries(${PROJECT_NAME} foobar::foobar)", content)

    def test_with_build_modules(self):
        conanfile = textwrap.dedent("""
                    import os
                    from conans import ConanFile

                    class HelloConan(ConanFile):
                        exports_sources = 'bm.cmake'
                        def package(self):
                            self.copy('bm.cmake', dst='lib/cmake')

                        def package_info(self):
                            self.cpp_info.set_property("cmake_file_name", "FooBar")
                            self.cpp_info.set_property("cmake_target_name", "foobar")
                            self.cpp_info.set_property("pkg_config_name", "foobar_cfg")
                            self.cpp_info.set_property('cmake_build_modules', ['lib/cmake/bm.cmake'])
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "bm.cmake": "Content of build_module" })
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertIn("#### lib/cmake/bm.cmake", content)
        self.assertIn("Content of build_module", content)

    def test_no_components(self):
        conanfile = textwrap.dedent("""
                    import os
                    from conans import ConanFile

                    class HelloConan(ConanFile):
                        def package_info(self):
                            self.cpp_info.set_property("cmake_target_name", "foobar")
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertNotIn("Or link just one of its components", content)
        self.assertNotIn("Declared components", content)

    def test_with_components(self):
        conanfile = textwrap.dedent("""
                    import os
                    from conans import ConanFile

                    class HelloConan(ConanFile):
                        def package_info(self):
                            self.cpp_info.set_property("cmake_target_name", "foobar")
                            self.cpp_info.components["component1"].set_property("cmake_target_name", "foobar::component_name")
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertIn("target_link_libraries(${PROJECT_NAME} foobar::component_name)", content)
        self.assertIn("* CMake target name: ``foobar::component_name``", content)

    def test_with_components_and_target_namespace(self):
        conanfile = textwrap.dedent("""
                    import os
                    from conans import ConanFile

                    class HelloConan(ConanFile):
                        def package_info(self):
                            self.cpp_info.set_property("cmake_target_name", "namespace::name")
                            self.cpp_info.components["component1"].set_property("cmake_target_name", "namespace::component_name")
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")

        self.assertIn("target_link_libraries(${PROJECT_NAME} namespace::name)", content)
        self.assertIn("* CMake target name: ``namespace::component_name``", content)

    def test_c_project(self):
        conanfile = textwrap.dedent("""
                    from conans import ConanFile
                    class HelloConan(ConanFile):
                        settings = "os", "arch", "compiler", "build_type"
                        def configure(self):
                            del self.settings.compiler.libcxx
                            del self.settings.compiler.cppstd
                        def package_info(self):
                            self.cpp_info.set_property("cmake_file_name", "FooBar")
                            self.cpp_info.set_property("cmake_target_name", "foobar")
                            self.cpp_info.set_property("pkg_config_name", "foobar_cfg")
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        content = client.load("bar.md")
        self.assertIn("main.c", content)
        self.assertIn("project(bar_project C)", content)

    def test_with_sys_requirements(self):
        conanfile = textwrap.dedent("""
                    import os
                    from conans import ConanFile

                    class HelloConan(ConanFile):
                        def package_info(self):
                            self.cpp_info.components["component1"].system_libs = ["system_lib"]
                    """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g markdown")
        assert "Generator markdown created bar.md" in client.out
