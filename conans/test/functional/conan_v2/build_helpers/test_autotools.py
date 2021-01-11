import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class AutotoolsBuildHelperTestCase(ConanV2ModeTestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile, AutoToolsBuildEnvironment, tools

        class Pkg(ConanFile):
            settings = "os", "arch", "{}"
            def run(cmd, *args, **kwargs):
                pass
            def build(self):
                autotools = AutoToolsBuildEnvironment(self)
                autotools.configure()
                autotools.make()
    """)

    def test_no_build_type(self):
        t = self.get_client()
        t.save({"conanfile.py": self.conanfile.format("compiler")})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: build_type setting should be defined.", t.out)

    def test_no_compiler(self):
        t = self.get_client()
        t.save({"conanfile.py": self.conanfile.format("build_type")})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: compiler setting should be defined.", t.out)
