import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_dependencies_visit():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . dep/0.1@")
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "dep/0.1"
            def generate(self):
                dep = self.dependencies.requires["dep"]
                self.output.info("DefRef: {}!!!".format(repr(dep.ref)))
                self.output.info("DefPRef: {}!!!".format(repr(dep.pref)))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("install .")
    assert "DefRef: dep/0.1#f3367e0e7d170aa12abccb175fee5f97!!!" in client.out
    assert "DefPRef: dep/0.1#f3367e0e7d170aa12abccb175fee5f97:"\
           "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"\
           "83c38d3b4e5f1b8450434436eec31b00!!!" in client.out
