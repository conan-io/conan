import os
import platform
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture()
def client():
    openssl = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            def package(self):
                with chdir(self.package_folder):
                    echo = "@echo off\necho MYOPENSSL={}!!".format(self.settings.os)
                    save("bin/myopenssl.bat", echo)
                    save("bin/myopenssl.sh", echo)
                    os.chmod("bin/myopenssl.sh", 0o777)
            """)

    cmake = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            requires = "openssl/1.0"
            def package(self):
                with chdir(self.package_folder):
                    echo = "@echo off\necho MYCMAKE={}!!".format(self.settings.os)
                    save("mycmake.bat", echo + "\ncall myopenssl.bat")
                    save("mycmake.sh", echo + "\n myopenssl.sh")
                    os.chmod("mycmake.sh", 0o777)

            def package_info(self):
                # Custom buildenv not defined by cpp_info
                self.buildenv_info.prepend_path("PATH", self.package_folder)
                self.buildenv_info.define("MYCMAKEVAR", "MYCMAKEVALUE!!")
            """)

    gtest = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            def package(self):
                with chdir(self.package_folder):
                    echo = "@echo off\necho MYGTEST={}!!".format(self.settings.os)
                    save("bin/mygtest.bat", echo)
                    save("bin/mygtest.sh", echo)
                    os.chmod("bin/mygtest.sh", 0o777)

            def package_info(self):
                self.runenv_info.define("MYGTESTVAR", "MyGTestValue{}".format(self.settings.os))
            """)
    client = TestClient()
    client.save({"cmake/conanfile.py": cmake,
                 "gtest/conanfile.py": gtest,
                 "openssl/conanfile.py": openssl})

    client.run("export openssl openssl/1.0@")
    client.run("export cmake mycmake/1.0@")
    client.run("export gtest mygtest/1.0@")

    myrunner_bat = "@echo off\necho MYGTESTVAR=%MYGTESTVAR%!!\n"
    myrunner_sh = "echo MYGTESTVAR=$MYGTESTVAR!!\n"
    client.save({"myrunner.bat": myrunner_bat,
                 "myrunner.sh": myrunner_sh}, clean_first=True)
    os.chmod(os.path.join(client.current_folder, "myrunner.sh"), 0o777)
    return client


def test_complete(client):
    conanfile = textwrap.dedent("""
        import platform
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            build_requires = "mycmake/1.0"
            apply_env = False

            def build_requirements(self):
                self.build_requires("mygtest/1.0", force_host_context=True)

            def build(self):
                mybuild_cmd = "mycmake.bat" if platform.system() == "Windows" else "mycmake.sh"
                self.run(mybuild_cmd)
                mytest_cmd = "mygtest.bat" if platform.system() == "Windows" else "mygtest.sh"
                self.run(mytest_cmd, env="conanrunenv")
       """)

    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Windows -s:h os=Linux --build=missing")
    # Run the BUILD environment
    ext = "bat" if platform.system() == "Windows" else "sh"  # TODO: Decide on logic .bat vs .sh
    cmd = environment_wrap_command("conanbuildenv", "mycmake.{}".format(ext),
                                   cwd=client.current_folder)
    client.run_command(cmd)
    assert "MYCMAKE=Windows!!" in client.out
    assert "MYOPENSSL=Windows!!" in client.out

    # Run the RUN environment
    cmd = environment_wrap_command("conanrunenv",
                                   "mygtest.{ext} && .{sep}myrunner.{ext}".format(ext=ext,
                                                                                  sep=os.sep),
                                   cwd=client.current_folder)
    client.run_command(cmd)
    assert "MYGTEST=Linux!!" in client.out
    assert "MYGTESTVAR=MyGTestValueLinux!!" in client.out

    client.run("build .")
    assert "MYCMAKE=Windows!!" in client.out
    assert "MYOPENSSL=Windows!!" in client.out
    assert "MYGTEST=Linux!!" in client.out


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
    cmd = environment_wrap_command("conanbuildenv", "mycompiler.{}".format(ext),
                                   cwd=client.current_folder)
    client.run_command(cmd)
    assert "MYCOMPILER!!" in client.out
    assert "MYPATH=" in client.out

    # Now with pkg-specific env-var
    client.run("install . mypkg/1.0@  -pr=myprofile")
    client.run_command(cmd)
    assert "MYCOMPILER2!!" in client.out
    assert "MYPATH2=" in client.out


def test_transitive_order():
    gcc = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.runenv_info.append("MYVAR", "MyGCCValue")
        """)
    openssl = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            build_requires = "gcc/1.0"
            def package_info(self):
                self.runenv_info.append("MYVAR", "MyOpenSSL{}Value".format(self.settings.os))
        """)
    cmake = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            build_requires = "gcc/1.0"
            def package_info(self):
                self.runenv_info.append("MYVAR", "MyCMakeRunValue")
                self.buildenv_info.append("MYVAR", "MyCMakeBuildValue")
        """)
    client = TestClient()
    client.save({"gcc/conanfile.py": gcc,
                 "cmake/conanfile.py": cmake,
                 "openssl/conanfile.py": openssl})

    client.run("create gcc gcc/1.0@")
    client.run("create openssl openssl/1.0@ -s os=Windows")
    client.run("create openssl openssl/1.0@ -s os=Linux")
    client.run("create cmake cmake/1.0@")

    client.save({"conanfile.py": GenConanfile().with_requires("openssl/1.0")
                .with_build_requires("cmake/1.0")}, clean_first=True)
    client.run("install . -s:b os=Windows -s:h os=Linux -g VirtualEnv")
    ext = "bat" if platform.system() == "Windows" else "sh"
    buildenv = client.load("conanbuildenv.{}".format(ext))
    assert "MyOpenSSLWindowsValue MyCMakeBuildValue" in buildenv
    assert "MyGCCValue" not in buildenv
    runenv = client.load("conanrunenv.{}".format(ext))
    assert "MyOpenSSLLinuxValue" in runenv
    assert "MyCMake" not in runenv
    assert "MyGCCValue" not in runenv
