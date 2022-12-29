import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class DeprecatedTestCase(unittest.TestCase):
    def test_no_deprecated(self):
        t = TestClient()
        t.save({'taskflow.py': GenConanfile("cpp-taskflow", "1.0").with_deprecated("''")})
        t.run("create taskflow.py")

        self.assertNotIn("Please, consider changing your requirements.", t.out)

    def test_deprecated_simple(self):
        t = TestClient()
        t.save({'taskflow.py': GenConanfile("cpp-taskflow", "1.0").with_deprecated("True")})
        t.run("create taskflow.py")

        self.assertIn("cpp-taskflow/1.0: WARN: Recipe 'cpp-taskflow/1.0' is deprecated. "
                      "Please, consider changing your requirements.", t.out)

        t.run("create taskflow.py conan/stable")
        self.assertIn("cpp-taskflow/1.0@conan/stable: WARN: Recipe 'cpp-taskflow/1.0@conan/stable' "
                      "is deprecated. Please, consider changing your requirements.", t.out)

    def test_deprecated_with(self):
        t = TestClient()
        t.save({'taskflow.py': GenConanfile("cpp-taskflow", "1.0").with_deprecated('"taskflow"')})
        t.run("create taskflow.py")

        self.assertIn("cpp-taskflow/1.0: WARN: Recipe 'cpp-taskflow/1.0' is deprecated in "
                      "favor of 'taskflow'. Please, consider changing your requirements.", t.out)

        t.run("create taskflow.py conan/stable")
        self.assertIn("cpp-taskflow/1.0@conan/stable: WARN: Recipe 'cpp-taskflow/1.0@conan/stable' "
                      "is deprecated in favor of 'taskflow'. Please, consider "
                      "changing your requirements.", t.out)
