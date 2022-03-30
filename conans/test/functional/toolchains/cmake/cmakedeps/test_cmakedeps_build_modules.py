import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
@pytest.mark.parametrize("use_components", [False, True])
def test_build_modules_alias_target(use_components):
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile

        class Conan(ConanFile):
            name = "hello"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = ["target-alias.cmake"]

            def package(self):
                self.copy("target-alias.cmake", dst="share/cmake")

            def package_info(self):
                module = os.path.join("share", "cmake", "target-alias.cmake")
                {}
        """)
    if use_components:
        info = """
        self.cpp_info.components["comp"].set_property("cmake_build_modules", [module])
        """
    else:
        info = """
        self.cpp_info.set_property("cmake_build_modules", [module])
        """
    target_alias = textwrap.dedent("""
        add_library(otherhello INTERFACE IMPORTED)
        target_link_libraries(otherhello INTERFACE {target_name})
        """).format(target_name="namespace::comp" if use_components else "hello::hello")
    conanfile = conanfile.format(info)
    client.save({"conanfile.py": conanfile, "target-alias.cmake": target_alias})
    client.run("create .")

    consumer = textwrap.dedent("""
        from conans import ConanFile, CMake

        class Conan(ConanFile):
            name = "consumer"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = ["CMakeLists.txt"]
            generators = "CMakeDeps", "CMakeToolchain"
            requires = "hello/1.0"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.0)
        project(test)
        find_package(hello CONFIG)
        get_target_property(tmp otherhello INTERFACE_LINK_LIBRARIES)
        message("otherhello link libraries: ${tmp}")
        """)
    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run("create .")
    if use_components:
        assert "otherhello link libraries: namespace::comp" in client.out
    else:
        assert "otherhello link libraries: hello::hello" in client.out


@pytest.mark.tool_cmake
def test_build_modules_components_selection_is_not_possible():
    """
    If openssl declares different cmake_build_modules on ssl and crypto, in the consumer both
    are included even if the cpp_info of the consumer declares:
        def package_info(self):
            self.cpp_info.requires = ["openssl::crypto"]
    Because that information is defined later, not at "generate" time (building time).
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile

        class Conan(ConanFile):
            name = "openssl"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = ["ssl.cmake", "crypto.cmake", "root.cmake"]

            def package(self):
                self.copy("*.cmake", dst="share/cmake")

            def package_info(self):
                ssl_module = os.path.join("share", "cmake", "ssl.cmake")
                self.cpp_info.components["ssl"].set_property("cmake_build_modules", [ssl_module])

                crypto_module = os.path.join("share", "cmake", "crypto.cmake")
                self.cpp_info.components["crypto"].set_property("cmake_build_modules", [crypto_module])

                root_module = os.path.join("share", "cmake", "root.cmake")
                self.cpp_info.set_property("cmake_build_modules", [root_module])
        """)

    ssl_cmake = textwrap.dedent("""
        function(ssl_message MESSAGE_OUTPUT)
            message("SSL MESSAGE:${ARGV${0}}")
        endfunction()
        """)
    crypto_cmake = textwrap.dedent("""
        function(crypto_message MESSAGE_OUTPUT)
            message("CRYPTO MESSAGE:${ARGV${0}}")
        endfunction()
        """)
    root_cmake = textwrap.dedent("""
        function(root_message MESSAGE_OUTPUT)
            message("ROOT MESSAGE:${ARGV${0}}")
        endfunction()
        """)
    client.save({"conanfile.py": conanfile,
                 "ssl.cmake": ssl_cmake,
                 "crypto.cmake": crypto_cmake,
                 "root.cmake": root_cmake})
    client.run("create .")

    consumer = textwrap.dedent("""
        from conans import ConanFile, CMake

        class Conan(ConanFile):
            name = "consumer"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = ["CMakeLists.txt"]
            generators = "CMakeDeps", "CMakeToolchain"
            requires = "openssl/1.0"

            def build(self):
                cmake = CMake(self)
                cmake.configure()

            def package_info(self):
                self.cpp_info.requires = ["openssl::crypto"]
        """)

    cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test)
            find_package(openssl CONFIG)
            crypto_message("hello!")
            ssl_message("hello!")
            root_message("hello!")
            """)
    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    # As we are requiring only "crypto" but it doesn't matter, it is not possible to include
    # only crypto build_modules
    client.run("create .")
    assert "SSL MESSAGE:hello!" in client.out
    assert "CRYPTO MESSAGE:hello!" in client.out
    assert "ROOT MESSAGE:hello!" in client.out

