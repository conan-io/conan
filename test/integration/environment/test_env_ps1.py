import os
import platform
import textwrap

from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.tools import TestClient, GenConanfile
from conan.tools.env.environment import environment_wrap_command

script_ext = ".bat" if platform.system() == "Windows" else ".sh"


def test_ps1_consumer_and_test_package():
    c = TestClient()
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "conanfile.txt": "[tool_requires]\ntool/0.1\n[generators]\nVirtualBuildEnv\n",
            "profile": "[buildenv]\nMYVAR=1\n"})
    c.run("create tool")
    c.run("install . -pr=profile")
    files = sorted(f for f in os.listdir(c.current_folder) if f.startswith("conan"))
    assert "conanbuild.ps1" in files
    assert "conanbuild" + script_ext in files
    ps1s = [f for f in files if f.endswith(".ps1")]
    assert "conanbuildenv.ps1" in ps1s
    for f in ps1s:  # all .ps1 have the equivalent .bat/.sh
        assert (os.path.splitext(f)[0] + ".bat" in files
                or os.path.splitext(f)[0] + ".sh" in files)


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
    c.run("create .")
    build = [line for line in c.out.splitlines() if "BUILD:" in line][0]
    test = [line for line in c.out.splitlines() if "TEST:" in line][0]
    assert ".ps1" not in build
    assert "conanrun.ps1" in test
    # With the conf, they are generated also for the dependencies
    c.run("create . -c tools.env.virtualenv:powershell=powershell.exe")
    build = [line for line in c.out.splitlines() if "BUILD:" in line][0]
    assert "conanbuild.ps1" in build


def test_ps1_only_used_with_powershell_conf():
    c = TestClient()
    c.save({"conanfile.txt": "[generators]\nVirtualBuildEnv\n",
            "profile": "[buildenv]\nMYVAR=1\n"})
    c.run("install . -pr=profile")
    # By default, Conan commands use the .bat/.sh
    cmd = environment_wrap_command(ConanFileMock(), "conanbuild", c.current_folder, "echo hello")
    assert "conanbuild" + script_ext in cmd
    assert ".ps1" not in cmd
    # Only if defined, it will use the .ps1
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.env.virtualenv:powershell", "powershell.exe")
    cmd = environment_wrap_command(conanfile, "conanbuild", c.current_folder, "echo hello")
    assert "conanbuild.ps1" in cmd
    assert script_ext not in cmd  # only the .ps1, not both
