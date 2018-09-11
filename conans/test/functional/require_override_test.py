import unittest

from conans.test.utils.tools import TestClient

base_conanfile = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "%s"
    version = "%s"
    build_policy = "missing"
    requires = %s
"""

base_conanfile_method = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "%s"
    version = "%s"
    build_policy = "missing"
    
    def requirements(self):
        %s
"""


class RequireOverrideTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _save(self, name, version, req_method, requires=None):
        reqs = []
        if not req_method:
            requires = requires or []
            text = "("
            for req in requires:
                if isinstance(req, str):
                    reqs.append('"%s"' % str(req))
                else:
                    reqs.append(str(req))
            text += ', '.join(reqs)
            text += ")"
            tmp = base_conanfile % (name, version, text)
        else:
            requires = requires or []
            for req in requires:
                if isinstance(req, str):
                    reqs.append('self.requires("%s")' % str(req))
                else:
                    reqs.append('self.requires("%s", override="%s")' % (req[0], req[1]))
            text = '\n        '.join(reqs) if reqs else "pass"
            tmp = base_conanfile_method % (name, version, text)
        self.client.save({"conanfile.py": tmp}, clean_first=True)

    def _save_and_export(self, name, version, req_method, requires=None, ):
        self._save(name, version, req_method, requires)
        self.client.run("export . user/channel")

    def test_override(self):
        for req_method in (False, True):
            self._save_and_export("libA", "1.0", req_method)
            self._save_and_export("libA", "2.0", req_method)
            self._save_and_export("libB", "1.0", req_method, ["libA/1.0@user/channel"])
            self._save_and_export("libC", "1.0", req_method, ["libA/2.0@user/channel"])
            self._save("project", "1.0", req_method, ["libB/1.0@user/channel",
                                                      "libC/1.0@user/channel"])
            error = self.client.run("create . user/channel", ignore_error=True)
            self.assertTrue(error)
            self.assertIn("Requirement libA/2.0@user/channel conflicts with "
                          "already defined libA/1.0@user/channel", self.client.out)

            self._save("project", "1.0", req_method, ["libB/1.0@user/channel",
                                                      "libC/1.0@user/channel",
                                                      ("libA/1.0@user/channel", "override")])
            self.client.run("create . user/channel")
            self.assertIn("libA/2.0@user/channel overridden by project/1.0@user/channel",
                          self.client.out)
