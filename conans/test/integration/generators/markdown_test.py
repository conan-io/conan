import textwrap

from conans.test.utils.tools import TestClient


def test_cmake_find_filename():
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

    assert "find_package(FooBar)" in content
    assert "target_link_libraries(<target_name> foobar)" in content


def test_cmake_find_filename_with_namespace():
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

    assert "find_package(FooBar)" in content
    assert "target_link_libraries(<target_name> foobar::foobar)" in content


def test_c_project():
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
    assert "main.c" in content


def test_with_build_modules():
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

    assert "* `lib/cmake/bm.cmake`" in content
    assert "Content of build_module" in content


def test_no_components():
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

    assert "Or link just one of its components" not in content
    assert "Declared components" in content


def test_with_components():
    conanfile = textwrap.dedent("""
                import os
                from conans import ConanFile

                class HelloConan(ConanFile):
                    def package_info(self):
                        self.cpp_info.set_property("cmake_target_name", "foobar")
                        self.cpp_info.components["component1"].set_property("cmake_target_name", "foobar::component_name1")
                        self.cpp_info.components["component2"].set_property("cmake_target_name", "foobar::component_name2")
                        self.cpp_info.components["component3"].set_property("cmake_target_name", "foobar::component_name3")
                        self.cpp_info.components["component4"].set_property("cmake_target_name", "foobar::component_name4")
                        self.cpp_info.components["component5"].set_property("cmake_target_name", "foobar::component_name5")
                """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . bar/0.1.0@user/testing")
    client.run("install bar/0.1.0@user/testing -g markdown")
    content = client.load("bar.md")

    assert "target_link_libraries(<target_name> foobar::component_name)" in content
    assert "* Component ``foobar::component_name``" in content


def test_with_components_and_target_namespace():
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

    assert "target_link_libraries(<target_name> namespace::component_name)" in content
    assert "* Component ``namespace::component_name``" in content
