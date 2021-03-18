import os
import platform
import textwrap


from conan.tools.env.environment import environment_wrap_command
from conans.test.utils.tools import TestClient


def test_profile_buildenv():
    client = TestClient()
    conanfile = textwrap.dedent("""\
        import os, platform
        from conans import ConanFile
        class Pkg(ConanFile):
            def generate(self):
                if platform.system() == "Windows":
                    self.buildenv.save_bat("pkgenv.bat")
                else:
                    self.buildenv.save_sh("pkgenv.sh")
                    os.chmod("pkgenv.sh", 0o777)

        """)
    # Some scripts in a random system folders, path adding to the profile [env]

    compiler_bat = "@echo off\necho MYCOMPILER!!\necho MYPATH=%PATH%"
    compiler_sh = "echo MYCOMPILER!!\necho MYPATH=$PATH"
    compiler2_bat = "@echo off\necho MYCOMPILER2!!\necho MYPATH2=%PATH%"
    compiler2_sh = "echo MYCOMPILER2!!\necho MYPATH2=$PATH"

    myprofile = textwrap.dedent("""
           [buildenv]
           PATH+=(path){}
           mypkg*:PATH=!
           mypkg*:PATH+=(path){}
           """.format(os.path.join(client.current_folder, "compiler"),
                      os.path.join(client.current_folder, "compiler2")))
    client.save({"conanfile.py": conanfile,
                 "myprofile": myprofile,
                 "compiler/mycompiler.bat": compiler_bat,
                 "compiler/mycompiler.sh": compiler_sh,
                 "compiler2/mycompiler.bat": compiler2_bat,
                 "compiler2/mycompiler.sh": compiler2_sh})

    os.chmod(os.path.join(client.current_folder, "compiler", "mycompiler.sh"), 0o777)
    os.chmod(os.path.join(client.current_folder, "compiler2", "mycompiler.sh"), 0o777)

    client.run("install . -pr=myprofile")
    # Run the BUILD environment
    ext = "bat" if platform.system() == "Windows" else "sh"  # TODO: Decide on logic .bat vs .sh
    cmd = environment_wrap_command("pkgenv", "mycompiler.{}".format(ext), cwd=client.current_folder)
    client.run_command(cmd)
    assert "MYCOMPILER!!" in client.out
    assert "MYPATH=" in client.out

    # Now with pkg-specific env-var
    client.run("install . mypkg/1.0@  -pr=myprofile")
    client.run_command(cmd)
    assert "MYCOMPILER2!!" in client.out
    assert "MYPATH2=" in client.out
