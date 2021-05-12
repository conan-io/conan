import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient, GenConanfile


@pytest.mark.xfail(reason="To be moved to core graph tests, except some UX reporting tests")
class ConditionalProvidesTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            requires = 'req/v1'
            options = {'conflict': [True, False]}
            default_options = {'conflict': False}

            def configure(self):
                if self.options.conflict:
                    self.provides = 'libjpeg'

            def package_info(self):
                self.info.header_only()
    """)

    def test_conflict_requirement(self):
        t = TestClient()
        t.save({'requires.py': GenConanfile("req", "v1").with_provides("libjpeg"),
                'app.py': self.conanfile})
        t.run("create requires.py")
        t.run("install app.py app/version@")
        t.run("install app.py app/version@ -o app:conflict=True", assert_error=True)
        self.assertIn(" - 'libjpeg' provided by 'app.py (app/version)', 'req/v1'", t.out)
