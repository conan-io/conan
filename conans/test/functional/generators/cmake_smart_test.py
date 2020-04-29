import os
import platform
import textwrap
import unittest

import six
from nose.plugins.attrib import attr

from conans.client.tools import replace_in_file
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


class CMakeSmartGeneratorTest(unittest.TestCase):

    def cmake_smart_test(self):
        conanfile = textwrap.dedent("""
        from conans import ConanFile, tools, CMake

        class ZLib(ConanFile):
            name = "zlib"
            version = "0.1"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "*.lib"

            def package(self):
                self.copy("*.lib", dst="lib")

            def package_info(self):
                self.cpp_info.names["cmake_smart"] = "ZLIB"
                self.cpp_info.libs.append("zlib")
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile, "zlib.lib": ""})
        client.run("create . user/channel")

        conanfile = textwrap.dedent("""
        from conans import ConanFile, tools, CMake

        class OpenSSL(ConanFile):
            name = "openssl"
            version = "0.1"
            requires = "zlib/0.1@user/channel"
            generators = "cmake_smart"
            exports_sources = "CMakeLists.txt", "*.lib"
            settings = "os", "arch", "compiler"

            def package(self):
                self.copy("*.lib", dst="lib")

            def package_info(self):
                self.cpp_info.names["cmake_smart"] = "OpenSSL"
                self.cpp_info.components["ssl"].names["cmake_smart"] = "SSL"
                self.cpp_info.components["ssl"].libs.append("mylibssl")
                self.cpp_info.components["crypto"].names["cmake_smart"] = "Crypto"
                self.cpp_info.components["crypto"].libs.append("crypto")
                #self.cpp_info.components["crypto"].requires = ["::ssl", "zlib::zlib"]
        """)

        client.save({"conanfile.py": conanfile, "mylibssl.lib": "", "crypto.lib": ""})
        client.run("create . user/channel")

        conanfile = textwrap.dedent("""
        from conans import ConanFile, tools, CMake

        class Libcurl(ConanFile):
            name = "libcurl"
            version = "0.1"
            requires = "openssl/0.1@user/channel"
            generators = "cmake_smart"
            exports_sources = "CMakeLists.txt"
            settings = "os", "arch", "compiler"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
        cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.1)
        project(consumer)
        find_package(OpenSSL)
        message("OpenSSL libraries to link: ${OpenSSL_LIBRARIES}")
        message("OpenSSL Version: ${OpenSSL_VERSION}")
        
        get_target_property(tmp ZLIB::ZLIB INTERFACE_LINK_LIBRARIES)
        message("Target ZLIB::ZLIB libs: ${tmp}")
        
        get_target_property(tmp OpenSSL::OpenSSL INTERFACE_LINK_LIBRARIES)
        message("Target OpenSSL::OpenSSL libs: ${tmp}")
        
        get_target_property(tmp OpenSSL::OpenSSL INTERFACE_COMPILE_OPTIONS)
        message("Compile options: ${tmp}")
        
        get_target_property(tmp OpenSSL::Crypto INTERFACE_LINK_LIBRARIES)
        message("Target OpenSSL::Crypto libs: ${tmp}")
        """)
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("create . user/channel")
        print(client.out)
        self.assertIn("OpenSSL libraries to link: crypto;libssl")
