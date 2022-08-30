import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
def test_build_modules_alias_target():
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
                self.cpp_info.set_property("cmake_build_modules", [module])
        """)

    target_alias = textwrap.dedent("""
        add_library(otherhello INTERFACE IMPORTED)
        target_link_libraries(otherhello INTERFACE hello::hello)
        """)
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
    assert "otherhello link libraries: hello::hello" in client.out


@pytest.mark.tool_cmake
def test_build_modules_components_is_not_possible():
    """
    The "cmake_build_module" property declared in the components is useless
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile

        class Conan(ConanFile):
            name = "openssl"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = ["crypto.cmake", "root.cmake"]

            def package(self):
                self.copy("*.cmake", dst="share/cmake")

            def package_info(self):
                crypto_module = os.path.join("share", "cmake", "crypto.cmake")
                self.cpp_info.components["crypto"].set_property("cmake_build_modules", [crypto_module])

                root_module = os.path.join("share", "cmake", "root.cmake")
                self.cpp_info.set_property("cmake_build_modules", [root_module])
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
            root_message("hello!")
            """)
    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    # As we are requiring only "crypto" but it doesn't matter, it is not possible to include
    # only crypto build_modules
    client.run("create .", assert_error=True)
    assert 'Unknown CMake command "crypto_message"' in client.out

    # Comment the function call
    client.save({"CMakeLists.txt": cmakelists.replace("crypto", "#crypto")})
    assert "ROOT MESSAGE:hello!" not in client.out

