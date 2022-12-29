import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class RequiresPrivateTestCase(unittest.TestCase):

    def test_conflict_branches_private(self):
        t = TestClient()
        t.save({'lhs.py': GenConanfile("lhs", "v1").with_provides("libjpeg"),
                'rhs.py': GenConanfile("rhs", "v1").with_provides("libjpeg"),
                'app.py': GenConanfile().with_require("lhs/v1", private=True)
                                        .with_require("rhs/v1", private=True)})
        t.run("export lhs.py")
        t.run("export rhs.py")
        t.run("install app.py app/version@", assert_error=True)
        self.assertIn(" - 'libjpeg' provided by 'lhs/v1', 'rhs/v1'", t.out)

    def test_conflict_transitive(self):
        t = TestClient()
        t.save({'top.py': GenConanfile("top", "v1").with_provides("libjpeg"),
                'middle.py': GenConanfile("middle", "v1").with_require("top/v1", private=True),
                'app.py': GenConanfile().with_provides("libjpeg")
                                        .with_require("middle/v1", private=True)})
        t.run("export top.py")
        t.run("export middle.py middle/v1@")
        t.run("install app.py app/version@ --build=missing")
