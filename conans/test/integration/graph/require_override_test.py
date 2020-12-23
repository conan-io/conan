import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class RequireOverrideTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _save(self, req_method, requires):
        conanfile = GenConanfile()
        for req in requires:
            req2, override = req if isinstance(req, tuple) else (req, False)
            if not req_method:
                conanfile.with_require(req2, override=override)
            else:
                conanfile.with_requirement(req2, override=override)
        self.client.save({"conanfile.py": conanfile}, clean_first=True)

    def test_override(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("export . libA/1.0@user/channel")
        # It is necessary to create libA/2.0 to have a conflict, otherwise it is missing
        self.client.run("export . libA/2.0@user/channel")

        for req_method in (False, True):
            self._save(req_method, ["libA/1.0@user/channel"])
            self.client.run("export . libB/1.0@user/channel")
            self._save(req_method, ["libA/2.0@user/channel"])
            self.client.run("export . libC/1.0@user/channel")
            self._save(req_method, ["libB/1.0@user/channel", "libC/1.0@user/channel"])
            self.client.run("info .", assert_error=True)
            self.assertIn("Conflict in libC/1.0@user/channel:\n"
                "    'libC/1.0@user/channel' requires 'libA/2.0@user/channel' while "
                "'libB/1.0@user/channel' requires 'libA/1.0@user/channel'.\n"
                "    To fix this conflict you need to override the package 'libA' in your root"
                " package.", self.client.out)

            self._save(req_method, ["libB/1.0@user/channel", "libC/1.0@user/channel",
                                    ("libA/1.0@user/channel", "override")])
            self.client.run("info .")
            self.assertIn("libA/2.0@user/channel overridden", self.client.out)

    def test_public_deps(self):
        client = TestClient()
        pkg2 = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                requires = ("pkg/0.1@user/stable", "override"),
                def package_info(self):
                    self.output.info("PUBLIC PKG2:%s" % self.cpp_info.public_deps)
            """)
        client.save({"conanfile.py": pkg2})
        client.run("create . pkg2/0.1@user/stable")
        self.assertIn("pkg2/0.1@user/stable: PUBLIC PKG2:[]", client.out)
        pkg3 = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                requires = "pkg2/0.1@user/stable", ("pkg/0.1@user/stable", "override")
                generators = "cmake"
            """)
        client.save({"conanfile.py": pkg3})
        client.run("install .")
        self.assertIn("pkg2/0.1@user/stable: PUBLIC PKG2:[]", client.out)
        conanbuildinfo = client.load("conanbuildinfo.cmake")
        self.assertIn("set(CONAN_DEPENDENCIES pkg2)", conanbuildinfo)
