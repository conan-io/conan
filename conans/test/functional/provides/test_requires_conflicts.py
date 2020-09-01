import unittest
import textwrap
import unittest

from jinja2 import Template

from conans.test.utils.tools import TestClient, GenConanfile


class RequiresConflictsTestCase(unittest.TestCase):
    header_only = Template(textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            requires = '{{ requires|join("', '") }}'
            def package_info(self):
                self.info.header_only()
    """))

    def test_conflict_requirement(self):
        t = TestClient()
        t.save({'requires.py': GenConanfile("req", "v1").with_provides("libjpeg"),
                'app.py': GenConanfile().with_provides("libjpeg")
               .with_require("req/v1")})
        t.run("export requires.py")
        t.run("install app.py app/version@", assert_error=True)
        self.assertIn(" - 'libjpeg' provided by 'app.py (app/version)', 'req/v1'", t.out)

    def test_conflict_transitive(self):
        t = TestClient()
        t.save({'top.py': GenConanfile("top", "v1").with_provides("libjpeg"),
                'middle.py': self.header_only.render(requires=['top/v1', ]),
                'app.py': GenConanfile().with_provides("libjpeg")
                                        .with_require("middle/v1")})
        t.run("export top.py")
        t.run("export middle.py middle/v1@")
        t.run("install app.py app/version@", assert_error=True)
        self.assertIn(" - 'libjpeg' provided by 'app.py (app/version)', 'top/v1'", t.out)

    def test_conflict_branches(self):
        t = TestClient()
        t.save({'lhs.py': GenConanfile("lhs", "v1").with_provides("libjpeg"),
                'rhs.py': GenConanfile("rhs", "v1").with_provides("libjpeg"),
                'app.py': GenConanfile().with_require("lhs/v1").with_require("rhs/v1")})
        t.run("export lhs.py")
        t.run("export rhs.py")
        t.run("install app.py app/version@", assert_error=True)
        self.assertIn(" - 'libjpeg' provided by 'lhs/v1', 'rhs/v1'", t.out)

    def test_conflict_branches_txt(self):
        t = TestClient()
        t.save({'lhs.py': GenConanfile("lhs", "v1").with_provides("libjpeg"),
                'rhs.py': GenConanfile("rhs", "v1").with_provides("libjpeg"),
                'conanfile.txt': "[requires]\nlhs/v1\nrhs/v1"})
        t.run("export lhs.py")
        t.run("export rhs.py")
        t.run("install conanfile.txt", assert_error=True)
        self.assertIn(" - 'libjpeg' provided by 'lhs/v1', 'rhs/v1'", t.out)
