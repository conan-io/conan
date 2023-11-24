import textwrap

from conans.test.utils.tools import TestClient


def test_deploy_method():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy, save
        class Pkg(ConanFile):
            name = "{name}"
            version = "0.1"
            {requires}
            def package(self):
                save(self, os.path.join(self.package_folder, f"my{name}file.txt"), "HELLO!!!!")
            def deploy(self):
                copy(self, "*", src=self.package_folder, dst=self.deploy_folder)
            """)
    c.save({"dep/conanfile.py": conanfile.format(name="dep", requires=""),
            "pkg/conanfile.py": conanfile.format(name="pkg", requires="requires='dep/0.1'")})
    c.run("create dep")
    assert "Executing deploy()" not in c.out
    c.run("create pkg")
    assert "Executing deploy()" not in c.out

    # Doesn't install by default
    c.run("install --requires=pkg/0.1")
    assert "Executing deploy()" not in c.out

    # Doesn't install with other patterns
    c.run("install --requires=pkg/0.1 --deployer-pkg=other")
    assert "Executing deploy()" not in c.out

    # install can deploy all
    c.run("install --requires=pkg/0.1 --deployer-pkg=* --deployer-folder=mydeploy")
    assert "dep/0.1: Executing deploy()" in c.out
    assert "pkg/0.1: Executing deploy()" in c.out
    assert c.load("mydeploy/mydepfile.txt") == "HELLO!!!!"
    assert c.load("mydeploy/mypkgfile.txt") == "HELLO!!!!"

    # install can deploy only "pkg"
    c.run("install --requires=pkg/0.1 --deployer-pkg=pkg/* --deployer-folder=mydeploy")
    print(c.out)
    assert "dep/0.1: Executing deploy()" not in c.out
    assert "pkg/0.1: Executing deploy()" in c.out
