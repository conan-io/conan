import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient, GenConanfile


@pytest.mark.xfail(reason="Overrides Output have changed")
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
        self.client.run("export . --name=liba --version=1.0 --user=user --channel=channel")
        # It is necessary to create liba/2.0 to have a conflict, otherwise it is missing
        self.client.run("export . --name=liba --version=2.0 --user=user --channel=channel")

        for req_method in (False, True):
            self._save(req_method, ["liba/1.0@user/channel"])
            self.client.run("export . --name=libb --version=1.0 --user=user --channel=channel")
            self._save(req_method, ["liba/2.0@user/channel"])
            self.client.run("export . --name=libC --version=1.0 --user=user --channel=channel")
            self._save(req_method, ["libb/1.0@user/channel", "libC/1.0@user/channel"])
            self.client.run("info .", assert_error=True)
            self.assertIn("Conflict in libC/1.0@user/channel:\n"
                "    'libC/1.0@user/channel' requires 'liba/2.0@user/channel' while "
                "'libb/1.0@user/channel' requires 'liba/1.0@user/channel'.\n"
                "    To fix this conflict you need to override the package 'libA' in your root"
                " package.", self.client.out)

            self._save(req_method, ["libb/1.0@user/channel", "libC/1.0@user/channel",
                                    ("liba/1.0@user/channel", "override")])
            self.client.run("info .")
            self.assertIn("liba/2.0@user/channel overridden", self.client.out)

    def test_can_override_even_versions_with_build_metadata(self):
        # https://github.com/conan-io/conan/issues/5900

        client = TestClient()
        client.save({"conanfile.py":
                    GenConanfile().with_name("libcore").with_version("1.0+abc")})
        client.run("create .")
        client.save({"conanfile.py":
                    GenConanfile().with_name("libcore").with_version("1.0+xyz")})
        client.run("create .")

        client.save({"conanfile.py":
                    GenConanfile().with_name("intermediate").
                    with_version("1.0").with_require("libcore/1.0+abc")})
        client.run("create .")

        client.save({"conanfile.py":
                    GenConanfile().with_name("consumer").
                    with_version("1.0").with_require("intermediate/1.0").
                    with_require("libcore/1.0+xyz")})
        client.run("create .")
        self.assertIn("WARN: intermediate/1.0: requirement libcore/1.0+abc "
                      "overridden by consumer/1.0 to libcore/1.0+xyz", client.out)
