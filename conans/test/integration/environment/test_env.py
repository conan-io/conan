import os
import platform
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.fixture()
def client():
    openssl = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            package_type = "shared-library"
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
    save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
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
                self.test_requires("mygtest/1.0")

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

    client.run("build . -s:b os=Windows -s:h os=Linux ")
    assert "MYCMAKE=Windows!!" in client.out
    assert "MYOPENSSL=Windows!!" in client.out
    assert "MYGTEST=Linux!!" in client.out


def test_profile_included_multiple():
    client = TestClient()
    conanfile = textwrap.dedent("""\
        import os, platform
        from conans import ConanFile
        class Pkg(ConanFile):
            def generate(self):
                buildenv = self.buildenv
                self.output.info("MYVAR1: {}!!!".format(buildenv.value("MYVAR1")))
                self.output.info("MYVAR2: {}!!!".format(buildenv.value("MYVAR2")))
                self.output.info("MYVAR3: {}!!!".format(buildenv.value("MYVAR3")))
        """)

    myprofile = textwrap.dedent("""
       [buildenv]
       MYVAR1=MyVal1
       MYVAR3+=MyVal3
       """)
    other_profile = textwrap.dedent("""
       [buildenv]
       MYVAR1=MyValOther1
       MYVAR2=MyValOther2
       MYVAR3=MyValOther3
       """)
    client.save({"conanfile.py": conanfile,
                 "myprofile": myprofile,
                 "myprofile_include": "include(other_profile)\n" + myprofile,
                 "other_profile": other_profile})
    # The reference profile has priority
    client.run("install . -pr=myprofile_include")
    assert "MYVAR1: MyVal1!!!" in client.out
    assert "MYVAR2: MyValOther2!!!" in client.out
    assert "MYVAR3: MyValOther3 MyVal3!!!" in client.out

    # Equivalent to include is to put it first, then the last has priority
    client.run("install . -pr=other_profile -pr=myprofile")
    assert "MYVAR1: MyVal1!!!" in client.out
    assert "MYVAR2: MyValOther2!!!" in client.out
    assert "MYVAR3: MyValOther3 MyVal3!!!" in client.out


def test_profile_buildenv():
    client = TestClient()
    save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
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
            package_type = "shared-library"
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

    client.run("export gcc gcc/1.0@")
    client.run("export openssl openssl/1.0@")
    client.run("export cmake cmake/1.0@")

    consumer = textwrap.dedent(r"""
        from conans import ConanFile
        from conan.tools.env import VirtualEnv
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            build_requires = "cmake/1.0", "gcc/1.0"
            def generate(self):
                env = VirtualEnv(self)
                buildenv = env.build_environment()
                self.output.info("BUILDENV: {}!!!".format(buildenv.value("MYVAR")))
                runenv = env.run_environment()
                self.output.info("RUNENV: {}!!!".format(runenv.value("MYVAR")))
        """)
    client.save({"conanfile.py": consumer}, clean_first=True)
    client.run("install . -s:b os=Windows -s:h os=Linux --build -g VirtualEnv")
    assert "BUILDENV: MYVAR MyGCCValue MyOpenSSLWindowsValue MyCMakeRunValue MyCMakeBuildValue!!!" in client.out
    assert "RUNENV: MYVAR MyOpenSSLLinuxValue!!!" in client.out


def test_buildenv_from_requires():
    openssl = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def package_info(self):
                self.buildenv_info.append("OpenSSL_ROOT",
                                          "MyOpenSSL{}Value".format(self.settings.os))
        """)
    poco = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            settings = "os"
            def package_info(self):
                self.buildenv_info.append("Poco_ROOT", "MyPoco{}Value".format(self.settings.os))
        """)
    client = TestClient()
    client.save({"poco/conanfile.py": poco,
                 "openssl/conanfile.py": openssl})

    client.run("export openssl openssl/1.0@")
    client.run("export poco poco/1.0@")

    consumer = textwrap.dedent(r"""
        from conans import ConanFile
        from conan.tools.env import VirtualEnv
        class Pkg(ConanFile):
            requires = "poco/1.0"
            def generate(self):
                env = VirtualEnv(self)
                buildenv = env.build_environment()
                self.output.info("BUILDENV POCO: {}!!!".format(buildenv.value("Poco_ROOT")))
                self.output.info("BUILDENV OpenSSL: {}!!!".format(buildenv.value("OpenSSL_ROOT")))
        """)
    client.save({"conanfile.py": consumer}, clean_first=True)
    client.run("install . -s:b os=Windows -s:h os=Linux --build -g VirtualEnv")
    assert "BUILDENV POCO: Poco_ROOT MyPocoLinuxValue!!!" in client.out
    assert "BUILDENV OpenSSL: OpenSSL_ROOT MyOpenSSLLinuxValue!!!" in client.out


@pytest.mark.xfail(reason="The VirtualEnv generator is not fully complete")
def test_diamond_repeated():
    pkga = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.runenv_info.define("MYVAR1", "PkgAValue1")
                self.runenv_info.append("MYVAR2", "PkgAValue2")
                self.runenv_info.prepend("MYVAR3", "PkgAValue3")
                self.runenv_info.prepend("MYVAR4", "PkgAValue4")
        """)
    pkgb = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "pkga/1.0"
            def package_info(self):
                self.runenv_info.append("MYVAR1", "PkgBValue1")
                self.runenv_info.append("MYVAR2", "PkgBValue2")
                self.runenv_info.prepend("MYVAR3", "PkgBValue3")
                self.runenv_info.prepend("MYVAR4", "PkgBValue4")
        """)
    pkgc = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "pkga/1.0"
            def package_info(self):
                self.runenv_info.append("MYVAR1", "PkgCValue1")
                self.runenv_info.append("MYVAR2", "PkgCValue2")
                self.runenv_info.prepend("MYVAR3", "PkgCValue3")
                self.runenv_info.prepend("MYVAR4", "PkgCValue4")
        """)
    pkgd = textwrap.dedent(r"""
       from conans import ConanFile
       class Pkg(ConanFile):
           requires = "pkgb/1.0", "pkgc/1.0"
           def package_info(self):
               self.runenv_info.append("MYVAR1", "PkgDValue1")
               self.runenv_info.append("MYVAR2", "PkgDValue2")
               self.runenv_info.prepend("MYVAR3", "PkgDValue3")
               self.runenv_info.define("MYVAR4", "PkgDValue4")
       """)
    pkge = textwrap.dedent(r"""
       from conans import ConanFile
       from conan.tools.env import VirtualEnv
       class Pkg(ConanFile):
           requires = "pkgd/1.0"
           def generate(self):
                env = VirtualEnv(self)
                runenv = env.run_environment()
                self.output.info("MYVAR1: {}!!!".format(runenv.value("MYVAR1")))
                self.output.info("MYVAR2: {}!!!".format(runenv.value("MYVAR2")))
                self.output.info("MYVAR3: {}!!!".format(runenv.value("MYVAR3")))
                self.output.info("MYVAR4: {}!!!".format(runenv.value("MYVAR4")))
       """)
    client = TestClient()
    client.save({"pkga/conanfile.py": pkga,
                 "pkgb/conanfile.py": pkgb,
                 "pkgc/conanfile.py": pkgc,
                 "pkgd/conanfile.py": pkgd,
                 "pkge/conanfile.py": pkge})

    client.run("export pkga pkga/1.0@")
    client.run("export pkgb pkgb/1.0@")
    client.run("export pkgc pkgc/1.0@")
    client.run("export pkgd pkgd/1.0@")

    client.run("install pkge --build")
    assert "MYVAR1: PkgAValue1 PkgCValue1 PkgBValue1 PkgDValue1!!!" in client.out
    assert "MYVAR2: MYVAR2 PkgAValue2 PkgCValue2 PkgBValue2 PkgDValue2!!!" in client.out
    assert "MYVAR3: PkgDValue3 PkgBValue3 PkgCValue3 PkgAValue3 MYVAR3!!!" in client.out
    assert "MYVAR4: PkgDValue4!!!" in client.out
