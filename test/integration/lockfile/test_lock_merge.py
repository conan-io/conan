import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_merge_alias(requires):
    """
    basic lockfile merging including alias
    """
    c = TestClient()
    app = textwrap.dedent(f"""
        from conan import ConanFile
        class App(ConanFile):
            settings = "build_type"
            def requirements(self):
                if self.settings.build_type == "Debug":
                    self.{requires}("pkg/(alias_debug)")
                else:
                    self.{requires}("pkg/(alias_release)")
        """)
    c.save({"pkg/conanfile.py": GenConanfile("pkg"),
            "alias_release/conanfile.py": GenConanfile("pkg", "alias_release").with_class_attribute(
                "alias = 'pkg/0.1'"),
            "alias_debug/conanfile.py": GenConanfile("pkg", "alias_debug").with_class_attribute(
                "alias = 'pkg/0.2'"),
            "app/conanfile.py": app})
    c.run("create pkg --version=0.1")
    c.run("create pkg --version=0.2")
    c.run("export alias_release")
    c.run("export alias_debug")
    c.run("lock create app -s build_type=Release --lockfile-out=release.lock")
    c.run("lock create app -s build_type=Debug --lockfile-out=debug.lock")

    c.run("lock merge --lockfile=release.lock --lockfile=debug.lock --lockfile-out=conan.lock")

    # Update alias, won't be used
    c.save({"alias_release/conanfile.py": GenConanfile("pkg", "alias_release").with_class_attribute(
                "alias = 'pkg/0.3'"),
            "alias_debug/conanfile.py": GenConanfile("pkg", "alias_debug").with_class_attribute(
                "alias = 'pkg/0.4'")})
    c.run("export alias_release")
    c.run("export alias_debug")

    # Merged one can resolve both aliased without issues
    c.run("install app -s build_type=Release --lockfile=conan.lock")
    is_build_requires = requires == "tool_requires"
    c.assert_listed_require({"pkg/0.1": "Cache"}, build=is_build_requires)
    c.run("install app -s build_type=Debug --lockfile=conan.lock")
    c.assert_listed_require({"pkg/0.2": "Cache"}, build=is_build_requires)

    # without lockfiles it would be pointing to the new (unexistent) ones
    c.run("install app -s build_type=Release", assert_error=True)
    assert "ERROR: Package 'pkg/0.3' not resolved" in c.out
    c.run("install app -s build_type=Debug", assert_error=True)
    assert "ERROR: Package 'pkg/0.4' not resolved" in c.out
