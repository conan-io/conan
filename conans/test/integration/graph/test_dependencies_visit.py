import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


def test_dependencies_visit():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . dep/0.1@")
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "dep/0.1"
            def generate(self):
                dep = self.dependencies["dep"]
                self.output.info("DefRef: {}!!!".format(repr(dep.ref)))
                self.output.info("DefPRef: {}!!!".format(repr(dep.pref)))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("install .")
    assert "DefRef: dep/0.1#f3367e0e7d170aa12abccb175fee5f97!!!" in client.out
    assert "DefPRef: dep/0.1#f3367e0e7d170aa12abccb175fee5f97:"\
           f"{NO_SETTINGS_PACKAGE_ID}#"\
           "cf924fbb5ed463b8bb960cf3a4ad4f3a!!!" in client.out
