from conans.test.utils.tools import TestClient, GenConanfile


class TestDeprecated:
    def test_no_deprecated(self):
        t = TestClient()
        t.save({'taskflow.py': GenConanfile("cpp-taskflow", "1.0").with_deprecated("''")})
        t.run("create taskflow.py")

        assert "Deprecated" not in t.out

    def test_deprecated_simple(self):
        t = TestClient()
        t.save({'taskflow.py': GenConanfile("cpp-taskflow", "1.0").with_deprecated("True")})
        t.run("create taskflow.py")

        assert "Deprecated\n    cpp-taskflow/1.0" in t.out

        t.run("create taskflow.py --user=conan --channel=stable")
        assert "Deprecated\n    cpp-taskflow/1.0" in t.out

    def test_deprecated_with(self):
        t = TestClient()
        t.save({'taskflow.py': GenConanfile("cpp-taskflow", "1.0").with_deprecated('"taskflow"')})
        t.run("create taskflow.py")

        assert "Deprecated\n    cpp-taskflow/1.0: taskflow" in t.out

        t.run("create taskflow.py --user=conan --channel=stable")
        assert "Deprecated\n    cpp-taskflow/1.0@conan/stable: taskflow" in t.out
