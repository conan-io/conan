from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestSystemHostOverrides:
    def test_system_tool_require(self):
        c = TestClient()
        c.save({"dep/conanfile.py": GenConanfile("dep2", "system"),
                "pkg/conanfile.py": GenConanfile().with_requires("dep1/1.0", "dep2/[>=1.0 <2]"),
                "profile": "[system_deps]\ndep1/1.0\ndep2/1.1: dep2/1.1@myteam/system"})
        c.run("create dep --user=myteam --channel=system")
        c.run("install pkg -pr=profile")
        print(c.out)
        assert "tool/1.0 - System tool" in c.out
