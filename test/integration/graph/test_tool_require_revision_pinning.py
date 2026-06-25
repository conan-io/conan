import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_tool_require_revision_pin_not_overridden_by_transitive():
    """
    https://github.com/conan-io/conan/issues/20060
    When a consumer pins a tool_require to a specific revision, that pin must be respected
    even if another tool_require earlier in the dependency graph requests the same package
    without a revision. The order of declarations should not matter.
    """
    c = TestClient()

    # Create foo/1.0 - first (old) revision
    c.save({"foo/conanfile.py": GenConanfile("foo", "1.0")})
    c.run("export foo")
    rev_old = c.exported_recipe_revision()

    # Create foo/1.0 - second (new) revision by changing the recipe
    c.save({"foo/conanfile.py": GenConanfile("foo", "1.0").with_class_attribute("myvar=42")})
    c.run("export foo")
    rev_new = c.exported_recipe_revision()
    assert rev_old != rev_new

    # bar/1.0 tool-requires foo/1.0 without any revision pin
    c.save({"bar/conanfile.py": GenConanfile("bar", "1.0").with_tool_requires("foo/1.0")})
    c.run("export bar")

    # Consumer declares bar first (which transitively pulls foo/1.0 at latest),
    # then explicitly pins foo/1.0#rev_old. The pin must win regardless of order.
    consumer = textwrap.dedent(f"""\
        from conan import ConanFile
        class Consumer(ConanFile):
            def build_requirements(self):
                self.tool_requires("bar/1.0")
                self.tool_requires("foo/1.0#{rev_old}")
        """)
    c.save({"consumer/conanfile.py": consumer})
    c.run("graph info consumer")

    # The explicitly pinned old revision must be selected, and also the latest one
    assert f"foo/1.0#{rev_old}" in c.out
    assert f"foo/1.0#{rev_new}" in c.out
