import textwrap

import pytest

from conan.test.utils.tools import TestClient, GenConanfile


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
        assert "WARN: risk: There are deprecated packages in the graph" in t.out

        t.run("create taskflow.py --user=conan --channel=stable")
        assert "Deprecated\n    cpp-taskflow/1.0" in t.out

    def test_deprecated_with(self):
        t = TestClient()
        t.save({'taskflow.py': GenConanfile("cpp-taskflow", "1.0").with_deprecated('"taskflow"')})
        t.run("create taskflow.py")

        assert "Deprecated\n    cpp-taskflow/1.0: taskflow" in t.out

        t.run("create taskflow.py --user=conan --channel=stable")
        assert "Deprecated\n    cpp-taskflow/1.0@conan/stable: taskflow" in t.out

    def test_deprecated_custom_text(self):
        tc = TestClient()
        tc.save({"old/conanfile.py": GenConanfile("maths", 1.0).with_deprecated('"This is not secure, use maths/[>=2.0]"'),
                 "new/conanfile.py": GenConanfile("maths", 2.0)})

        tc.run("create new/conanfile.py")
        tc.run("create old/conanfile.py")
        assert "maths/1.0: This is not secure, use maths/[>=2.0]" in tc.out
        tc.run("install --requires=maths/1.0")
        assert "maths/1.0: This is not secure, use maths/[>=2.0]" in tc.out

    def test_deprecated_configure(self):
        tc = TestClient()
        conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Version

        class Pkg(ConanFile):
            name = "pkg"

            def configure(self):
                if Version(self.version) < "1.0":
                    self.deprecated = True
        """)
        tc.save({"conanfile.py": conanfile})

        tc.run("graph info . --version=0.0")
        assert "deprecated: True" in tc.out

        tc.run("graph info . --version=2.0")
        assert "deprecated: None" in tc.out

class TestDeprecatedIncludesMessages:
    @pytest.mark.parametrize("import_stm,way", [
        ["from conans.model.package_ref import PkgReference", "PkgReference()"],
        ["from conans.model.package_ref import PkgReference", "PkgReference.loads('foo/1.0:123')"],
        ["from conans.model.recipe_ref import RecipeReference", "RecipeReference()"],
        ["from conans.model.recipe_ref import RecipeReference", "RecipeReference.loads('foo/1.0@user/channel')"]
    ])
    def test_deprecated_package_ref_include(self, import_stm, way):
        t = TestClient(light=True)
        t.save({"conanfile.py": GenConanfile("pkg", "0.1")
               .with_import(import_stm)
                .with_package_id(f"ref = {way}")})
        t.run("create conanfile.py")
        assert f"Private '{import_stm}'" in t.out
