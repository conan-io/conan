import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class CMakeBuildHelperTestCase(ConanV2ModeTestCase):

    def test_no_build_type(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class Pkg(ConanFile):
                settings = "os", "arch", "compiler"
                def build(self):
                    cmake = CMake(self)
                    cmake.build()
        """)
        t.save({"conanfile.py": conanfile})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: build_type setting should be defined.", t.out)

    def test_no_compiler(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            
            class Pkg(ConanFile):
                settings = "os", "arch", "build_type"
                def build(self):
                    cmake = CMake(self)
                    cmake.build()
        """)
        t.save({"conanfile.py": conanfile})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: compiler setting should be defined.", t.out)

    def test_toolchain_no_build_type(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class Pkg(ConanFile):
                toolchain = "cmake"
    
                def build(self):
                    cmake = CMake(self)
                    cmake.build()
        """)
        t.save({"conanfile.py": conanfile})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: build_type setting should be defined.", t.out)
