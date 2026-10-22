import os
import platform
import textwrap

from conan.test.utils.mocks import ConanFileMock
from conan.tools.env.environment import environment_wrap_command
from conan.test.utils.tools import TestClient, GenConanfile

script_ext = ".bat" if platform.system() == "Windows" else ".sh"


def _files(client):
    return sorted(f for f in os.listdir(client.current_folder) if f.startswith("conan"))


def test_consumer_ps1():
    c = TestClient()
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "conanfile.txt": "[tool_requires]\ntool/0.1\n[generators]\nVirtualBuildEnv\n"})
    c.run("create tool")
    c.run("install .")
    assert not [f for f in _files(c) if f.endswith(".ps1")]
    c.run("install . -c tools.env:ps1=True")
    files = _files(c)
    assert "conanbuild.ps1" in files
    assert "conanbuild" + script_ext in files
    ps1s = [f for f in files if f.endswith(".ps1") and not f.startswith("deactivate")]
    assert any(f.startswith("conanbuildenv-") for f in ps1s)
    for f in ps1s:  # all .ps1 have the equivalent .bat/.sh
        assert os.path.splitext(f)[0] + script_ext in files


def test_ps1_not_in_cache_but_in_test_package():
    c = TestClient()
    test_package = textwrap.dedent("""
        import os
        from conan import ConanFile
        class Test(ConanFile):
            generators = "VirtualRunEnv"
            def requirements(self):
                self.requires(self.tested_reference_str)
            def test(self):
                files = sorted(f for f in os.listdir(self.generators_folder) if "conan" in f)
                self.output.info(f"TEST: {files}")
        """)
    pkg = textwrap.dedent("""
        import os
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            generators = "VirtualBuildEnv"
            def build(self):
                files = sorted(f for f in os.listdir(self.generators_folder) if "conan" in f)
                self.output.info(f"BUILD: {files}")
        """)
    c.save({"conanfile.py": pkg, "test_package/conanfile.py": test_package})
    c.run("create . -c tools.env:ps1=True")
    build = [line for line in c.out.splitlines() if "BUILD:" in line][0]
    test = [line for line in c.out.splitlines() if "TEST:" in line][0]
    assert ".ps1" not in build
    assert "conanrun.ps1" in test
    assert "conanbuild.ps1" in test


def test_ps1_incompatible_with_powershell():
    c = TestClient()
    c.save({"conanfile.txt": "[generators]\nVirtualBuildEnv\n"})
    c.run("install . -c tools.env:ps1=True -c tools.env.virtualenv:powershell=powershell.exe",
          assert_error=True)
    assert "'tools.env:ps1' is incompatible with 'tools.env.virtualenv:powershell'" in c.out


def test_ps1_not_used_by_conan_commands():
    # Conan commands use the .bat/.sh, the .ps1 are only for the developers
    c = TestClient()
    c.save({"conanfile.txt": "[generators]\nVirtualBuildEnv\n",
            "profile": "[buildenv]\nMYVAR=1\n"})
    c.run("install . -pr=profile -c tools.env:ps1=True")
    assert os.path.isfile(os.path.join(c.current_folder, "conanbuild.ps1"))
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.env:ps1", True)
    cmd = environment_wrap_command(conanfile, "conanbuild", c.current_folder, "echo hello")
    assert "conanbuild" + script_ext in cmd
    assert ".ps1" not in cmd
    # without the conf, the .ps1 is still wrapped (explicit powershell scripts)
    cmd = environment_wrap_command(ConanFileMock(), "conanbuild", c.current_folder, "echo hello")
    assert "conanbuild.ps1" in cmd
