import unittest

from parameterized import parameterized

from conans.test.utils.tools import TestClient, GenConanfile


class BuildRequiresTestCase(unittest.TestCase):

    @parameterized.expand([(True,), (False,)])
    def test_build_require_lib(self, use_single_profile):
        t = TestClient()
        t.save({'br_lib.py': GenConanfile("br_lib", "v1").with_provides("libjpeg"),
                'br.py': GenConanfile("br", "v1").with_require("br_lib/v1"),
                'app.py': GenConanfile("app", "v1").with_build_requires("br/v1")
                                                   .with_provides("libjpeg")})
        t.run("create br_lib.py")
        t.run("create br.py")
        if use_single_profile:
            t.run("install app.py", assert_error=True)
            self.assertIn(" - 'libjpeg' provided by 'app.py (app/v1)', 'br_lib/v1'", t.out)
        else:
            t.run("install app.py --profile:host=default --profile:build=default")

    @parameterized.expand([(True,), (False,)])
    def test_build_require_host(self, use_single_profile):
        t = TestClient()
        t.save({'br_lib.py': GenConanfile("br_lib", "v1").with_provides("libjpeg"),
                'br.py': GenConanfile("br", "v1").with_require("br_lib/v1"),
                'app.py': GenConanfile("app", "v1").with_build_requirement("br/v1",
                                                                           force_host_context=True)
                                                   .with_provides("libjpeg")})
        t.run("create br_lib.py")
        t.run("create br.py")
        if use_single_profile:
            t.run("install app.py", assert_error=True)
        else:
            t.run("install app.py --profile:host=default --profile:build=default", assert_error=True)
        self.assertIn(" - 'libjpeg' provided by 'app.py (app/v1)', 'br_lib/v1'", t.out)

    @parameterized.expand([(True,), (False,)])
    def test_build_require_host_transitive(self, use_single_profile):
        t = TestClient()
        t.save({'br.py': GenConanfile("br", "v1").with_provides("libjpeg"),
                'lib.py': GenConanfile("lib", "v1").with_build_requirement("br/v1",
                                                                           force_host_context=True),
                'app.py': GenConanfile("app", "v1").with_require("lib/v1")
                                                   .with_provides("libjpeg")})
        t.run("export br.py")
        t.run("export lib.py")
        if use_single_profile:
            t.run("install app.py --build")
        else:
            t.run("install app.py --profile:host=default --profile:build=default --build")

    @parameterized.expand([(True,), (False,)])
    def test_build_require_branches(self, use_single_profile):
        t = TestClient()
        t.save({'br_lhs.py': GenConanfile("br_lhs", "v1").with_provides("libjpeg"),
                'br_rhs.py': GenConanfile("br_rhs", "v1").with_provides("libjpeg"),
                'app.py': GenConanfile("app", "v1").with_build_requires("br_lhs/v1")
                                                   .with_build_requires("br_rhs/v1")})
        t.run("create br_lhs.py")
        t.run("create br_rhs.py")
        if use_single_profile:
            t.run("install app.py", assert_error=True)
            self.assertIn(" - 'libjpeg' provided by 'br_lhs/v1', 'br_rhs/v1'", t.out)
        else:
            t.run("install app.py --profile:host=default --profile:build=default")

    def test_build_require_of_build_require(self):
        # Only makes sense for two profiles
        t = TestClient()
        t.save({'br_nested.py': GenConanfile("br_nested", "v1").with_provides("libjpeg"),
                'br.py': GenConanfile("br", "v1").with_provides("libjpeg")
                                                 .with_build_requires("br_nested/v1"),
                'app.py': GenConanfile("app", "v1").with_provides("libjpeg")
                                                   .with_build_requires("br/v1")})
        t.run("export br_nested.py")
        t.run("export br.py")
        t.run("install app.py --profile:host=default --profile:build=default --build")
