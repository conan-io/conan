import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_requires_traits():
    """ traits can be passed to self.requires(), but:
    - They have absolutely no effect
    - They are not checked to be correct or match expected 2.0 traits
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def requirements(self):
                self.requires("dep/1.0", transitive_headers=True)
        """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
            "consumer/conanfile.py": conanfile})
    c.run("create dep")
    # This should not crash
    c.run("install consumer")
    assert "dep/1.0" in c.out
