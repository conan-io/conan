import textwrap

from conans.test.utils.tools import TestClient


def test_build_requires_source():
    c = TestClient()
    tool = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import chdir, save

        class Tool(ConanFile):
            name = "tool"
            version = "0.1"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = f"@echo off\necho MY-TOOL! {self.name}/{self.version}!!"
                    save(self, "bin/mytool.bat", echo)
                    save(self, "bin/mytool.sh", echo)
                    os.chmod("bin/mytool.sh", 0o777)
        """)
    pkg = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.env import VirtualBuildEnv
        import platform

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            tool_requires = "tool/0.1"

            def source(self):
                cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
                self.run(cmd)
        """)
    c.save({"tool/conanfile.py": tool,
            "pkg/conanfile.py": pkg})
    c.run("create tool")
    c.run("create pkg")
    assert "MY-TOOL! tool/0.1" in c.out

    c.run("install pkg")  # to generate conanbuild script first, so it is available
    c.run("source pkg")
    assert "MY-TOOL! tool/0.1" in c.out


"""
ALTERNATIVE 1: in recipe, explicit
def source(self):
    cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
    with VirtualBuildEnv(conanfile).vars().apply():
        self.run(cmd)

- Need to bypass ``settings`` restriction in ``source()``
- we can make a nice helper ``with buildenv``
"""

"""
ALTERNATIVE 2: in recipe, attribute
inject_source_buildenv = True

def source(self):
    cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
    self.run(cmd)

- No need to bypass ``settings`` restriction in ``source()``
"""

"""
ALTERNATIVE 3: always, this should be the expected default behavior

def source(self):
    cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
    self.run(cmd)

- No need to bypass ``settings`` restriction in ``source()``
- We might want to do an opt-out, just in case?
"""

"""
ALTERNATIVE 4: global, controlled by conf

def source(self):
    cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
    self.run(cmd)

- No need to bypass ``settings`` restriction in ``source()``
- [conf] core.source:inject_buildenv=True/False
"""
