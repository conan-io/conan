import os
import platform
import subprocess
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conan.test.utils.tools import TestClient, GenConanfile


@pytest.fixture()
def client():
    openssl = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            package_type = "shared-library"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYOPENSSL={}!!".format(self.settings.os)
                    save(self, "bin/myopenssl.bat", echo)
                    save(self, "bin/myopenssl.sh", echo)
                    os.chmod("bin/myopenssl.sh", 0o777)
            """)

    cmake = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            requires = "openssl/1.0"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYCMAKE={}!!".format(self.settings.os)
                    save(self, "mycmake.bat", echo + "\ncall myopenssl.bat")
                    save(self, "mycmake.sh", echo + "\n myopenssl.sh")
                    os.chmod("mycmake.sh", 0o777)

            def package_info(self):
                # Custom buildenv not defined by cpp_info
                self.buildenv_info.prepend_path("PATH", self.package_folder)
                self.buildenv_info.define("MYCMAKEVAR", "MYCMAKEVALUE!!")
            """)

    gtest = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            def package(self):
                with chdir(self, self.package_folder):
                    prefix = "@echo off\n" if self.settings.os == "Windows" else ""
                    echo = "{}echo MYGTEST={}!!".format(prefix, self.settings.os)
                    save(self, "bin/mygtest.bat", echo)
                    save(self, "bin/mygtest.sh", echo)
                    os.chmod("bin/mygtest.sh", 0o777)

            def package_info(self):
                self.runenv_info.define("MYGTESTVAR", "MyGTestValue{}".format(self.settings.os))
            """)
    client = TestClient()
    client.save({"cmake/conanfile.py": cmake,
                 "gtest/conanfile.py": gtest,
                 "openssl/conanfile.py": openssl})

    client.run("export openssl --name=openssl --version=1.0")
    client.run("export cmake --name=mycmake --version=1.0")
    client.run("export gtest --name=mygtest --version=1.0")

    myrunner_bat = "@echo off\necho MYGTESTVAR=%MYGTESTVAR%!!\n"
    myrunner_sh = "echo MYGTESTVAR=$MYGTESTVAR!!\n"
    client.save({"myrunner.bat": myrunner_bat,
                 "myrunner.sh": myrunner_sh}, clean_first=True)
    os.chmod(os.path.join(client.current_folder, "myrunner.sh"), 0o777)
    return client


@pytest.mark.parametrize("gtest_run_true", [True, False])
def test_complete(client, gtest_run_true):
    """By default, a test require has the run=False trait, so the PATH to the bat cannot be
    accessed"""
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile

        class Pkg(ConanFile):
            requires = "openssl/1.0"
            tool_requires = "mycmake/1.0"

            def build_requirements(self):
                {}

            def build(self):
                self.run("mycmake.bat", env="conanbuildenv")
                assert os.path.exists(os.path.join(self.generators_folder, "conanrunenv.sh"))
       """)
    if gtest_run_true:
        test_require = 'self.test_requires("mygtest/1.0", run=True)'
    else:
        test_require = 'self.test_requires("mygtest/1.0")'

    conanfile = conanfile.format(test_require)
    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Windows -s:h os=Linux --build=missing")
    # Run the BUILD environment
    if platform.system() == "Windows":
        cmd = environment_wrap_command("conanbuildenv", client.current_folder, "mycmake.bat")
        client.run_command(cmd)
        assert "MYCMAKE=Windows!!" in client.out
        assert "MYOPENSSL=Windows!!" in client.out

    # Run the RUN environment
    if platform.system() != "Windows":
        cmd = environment_wrap_command("conanrunenv", client.current_folder,
                                       "mygtest.sh && .{}myrunner.sh".format(os.sep))
        client.run_command(cmd, assert_error=not gtest_run_true)
        if gtest_run_true:
            assert "MYGTEST=Linux!!" in client.out
            assert "MYGTESTVAR=MyGTestValueLinux!!" in client.out

    if platform.system() == "Windows":
        client.run("build . -s:h os=Linux")
        assert "MYCMAKE=Windows!!" in client.out
        assert "MYOPENSSL=Windows!!" in client.out


def test_profile_included_multiple():
    client = TestClient()
    conanfile = textwrap.dedent("""\
        import os, platform
        from conan import ConanFile
        class Pkg(ConanFile):
            def generate(self):
                buildenv = self.buildenv.vars(self)
                self.output.info("MYVAR1: {}!!!".format(buildenv.get("MYVAR1")))
                self.output.info("MYVAR2: {}!!!".format(buildenv.get("MYVAR2")))
                self.output.info("MYVAR3: {}!!!".format(buildenv.get("MYVAR3")))
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
    conanfile = textwrap.dedent("""\
        import os, platform
        from conan import ConanFile
        class Pkg(ConanFile):
            def generate(self):
                self.buildenv.vars(self).save_script("pkgenv")
                if platform.system() != "Windows":
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
    cmd = environment_wrap_command("conanbuildenv", client.current_folder,
                                   "mycompiler.{}".format(ext))
    client.run_command(cmd)
    assert "MYCOMPILER!!" in client.out
    assert "MYPATH=" in client.out

    # Now with pkg-specific env-var
    client.run("install . --name=mypkg --version=1.0 -pr=myprofile")
    client.run_command(cmd)
    assert "MYCOMPILER2!!" in client.out
    assert "MYPATH2=" in client.out


def test_transitive_order():
    # conanfile.py -(br)-> cmake -> openssl (unknown=static)
    #     \                    \-(br)-> gcc
    #      \--------(br)-> gcc
    #       \---------------------> openssl
    gcc = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.runenv_info.append("MYVAR", "MyGCCValue")
        """)
    openssl = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            tool_requires = "gcc/1.0"
            package_type = "shared-library"
            def package_info(self):
                self.runenv_info.append("MYVAR", "MyOpenSSL{}Value".format(self.settings.os))
        """)
    cmake = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            tool_requires = "gcc/1.0"
            def package_info(self):
                self.runenv_info.append("MYVAR", "MyCMakeRunValue")
                self.buildenv_info.append("MYVAR", "MyCMakeBuildValue")
        """)
    client = TestClient()
    client.save({"gcc/conanfile.py": gcc,
                 "cmake/conanfile.py": cmake,
                 "openssl/conanfile.py": openssl})

    client.run("export gcc --name=gcc --version=1.0")
    client.run("export openssl --name=openssl --version=1.0")
    client.run("export cmake --name=cmake --version=1.0")

    consumer = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.env import VirtualBuildEnv, VirtualRunEnv
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            tool_requires = "cmake/1.0", "gcc/1.0"
            def generate(self):
                buildenv = VirtualBuildEnv(self).vars()
                self.output.info("BUILDENV: {}!!!".format(buildenv.get("MYVAR")))
                runenv = VirtualRunEnv(self).vars()
                self.output.info("RUNENV: {}!!!".format(runenv.get("MYVAR")))
        """)
    client.save({"conanfile.py": consumer}, clean_first=True)
    client.run("install . -s:b os=Windows -s:h os=Linux --build='*'")
    assert "BUILDENV: MyOpenSSLWindowsValue MyGCCValue "\
           "MyCMakeRunValue MyCMakeBuildValue!!!" in client.out
    assert "RUNENV: MyOpenSSLLinuxValue!!!" in client.out

    # Even if the generator is duplicated in command line (it used to fail due to bugs)
    client.run("install . -s:b os=Windows -s:h os=Linux --build='*' -g VirtualRunEnv -g VirtualBuildEnv")
    assert "BUILDENV: MyOpenSSLWindowsValue MyGCCValue "\
           "MyCMakeRunValue MyCMakeBuildValue!!!" in client.out
    assert "RUNENV: MyOpenSSLLinuxValue!!!" in client.out


def test_buildenv_from_requires():
    openssl = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def package_info(self):
                self.buildenv_info.append("OpenSSL_ROOT",
                                          "MyOpenSSL{}Value".format(self.settings.os))
        """)
    poco = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            settings = "os"
            def package_info(self):
                self.buildenv_info.append("Poco_ROOT", "MyPoco{}Value".format(self.settings.os))
        """)
    client = TestClient()
    client.save({"poco/conanfile.py": poco,
                 "openssl/conanfile.py": openssl})

    client.run("export openssl --name=openssl --version=1.0")
    client.run("export poco --name=poco --version=1.0")

    consumer = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.env import VirtualBuildEnv
        class Pkg(ConanFile):
            requires = "poco/1.0"
            def generate(self):
                buildenv = VirtualBuildEnv(self).vars()
                self.output.info("BUILDENV POCO: {}!!!".format(buildenv.get("Poco_ROOT")))
                self.output.info("BUILDENV OpenSSL: {}!!!".format(buildenv.get("OpenSSL_ROOT")))
        """)
    client.save({"conanfile.py": consumer}, clean_first=True)
    client.run("install . -s:b os=Windows -s:h os=Linux --build='*' -g VirtualBuildEnv")
    assert "BUILDENV POCO: MyPocoLinuxValue!!!" in client.out
    assert "BUILDENV OpenSSL: MyOpenSSLLinuxValue!!!" in client.out


def test_diamond_repeated():
    pkga = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.runenv_info.define("MYVAR1", "PkgAValue1")
                self.runenv_info.append("MYVAR2", "PkgAValue2")
                self.runenv_info.prepend("MYVAR3", "PkgAValue3")
                self.runenv_info.prepend("MYVAR4", "PkgAValue4")
        """)
    pkgb = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "pkga/1.0"
            def package_info(self):
                self.runenv_info.append("MYVAR1", "PkgBValue1")
                self.runenv_info.append("MYVAR2", "PkgBValue2")
                self.runenv_info.prepend("MYVAR3", "PkgBValue3")
                self.runenv_info.prepend("MYVAR4", "PkgBValue4")
        """)
    pkgc = textwrap.dedent(r"""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "pkga/1.0"
            def package_info(self):
                self.runenv_info.append("MYVAR1", "PkgCValue1")
                self.runenv_info.append("MYVAR2", "PkgCValue2")
                self.runenv_info.prepend("MYVAR3", "PkgCValue3")
                self.runenv_info.prepend("MYVAR4", "PkgCValue4")
        """)
    pkgd = textwrap.dedent(r"""
       from conan import ConanFile
       class Pkg(ConanFile):
           requires = "pkgb/1.0", "pkgc/1.0"
           def package_info(self):
               self.runenv_info.append("MYVAR1", "PkgDValue1")
               self.runenv_info.append("MYVAR2", "PkgDValue2")
               self.runenv_info.prepend("MYVAR3", "PkgDValue3")
               self.runenv_info.define("MYVAR4", "PkgDValue4")
       """)
    pkge = textwrap.dedent(r"""
       from conan import ConanFile
       from conan.tools.env import VirtualRunEnv
       class Pkg(ConanFile):
           requires = "pkgd/1.0"
           def generate(self):
                env = VirtualRunEnv(self)
                runenv = env.vars(scope="run")
                self.output.info("MYVAR1: {}!!!".format(runenv.get("MYVAR1")))
                self.output.info("MYVAR2: {}!!!".format(runenv.get("MYVAR2")))
                self.output.info("MYVAR3: {}!!!".format(runenv.get("MYVAR3")))
                self.output.info("MYVAR4: {}!!!".format(runenv.get("MYVAR4")))
                env.generate()
       """)
    client = TestClient()
    client.save({"pkga/conanfile.py": pkga,
                 "pkgb/conanfile.py": pkgb,
                 "pkgc/conanfile.py": pkgc,
                 "pkgd/conanfile.py": pkgd,
                 "pkge/conanfile.py": pkge})

    client.run("export pkga --name=pkga --version=1.0")
    client.run("export pkgb --name=pkgb --version=1.0")
    client.run("export pkgc --name=pkgc --version=1.0")
    client.run("export pkgd --name=pkgd --version=1.0")

    client.run("install pkge --build=missing")
    # PkgB has higher priority (included first) so it is appended last and prepended first (wrtC)
    assert "MYVAR1: PkgAValue1 PkgCValue1 PkgBValue1 PkgDValue1!!!" in client.out
    assert "MYVAR2: PkgAValue2 PkgCValue2 PkgBValue2 PkgDValue2!!!" in client.out
    assert "MYVAR3: PkgDValue3 PkgBValue3 PkgCValue3 PkgAValue3!!!" in client.out
    assert "MYVAR4: PkgDValue4!!!" in client.out

    # No settings always sh
    conanrun = client.load("pkge/conanrunenv.sh")
    assert "PATH" not in conanrun
    assert 'export MYVAR1="PkgAValue1 PkgCValue1 PkgBValue1 PkgDValue1"' in conanrun
    assert 'export MYVAR2="$MYVAR2 PkgAValue2 PkgCValue2 PkgBValue2 PkgDValue2"' in conanrun
    assert 'export MYVAR3="PkgDValue3 PkgBValue3 PkgCValue3 PkgAValue3 $MYVAR3"' in conanrun
    assert 'export MYVAR4="PkgDValue4"' in conanrun


@pytest.mark.parametrize("require_run", [True, False])
def test_environment_scripts_generated_envvars(require_run):
    """If the regular require doesn't declare the 'run' trait, the conanrunenv won't be there,
    unless for example, the require_pkg has the pkg_type to Application"""
    consumer_pkg = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.env import VirtualBuildEnv, VirtualRunEnv
        class Pkg(ConanFile):
            settings = "os"
            requires = "require_pkg/1.0"
            tool_requires = "build_require_pkg/1.0"
            generators = "VirtualRunEnv", "VirtualBuildEnv"
        """)

    client = TestClient()
    conanfile_br = (GenConanfile().with_package_file("bin/myapp", "myexe")
                                  .with_package_file("lib/mylib", "mylibcontent")
                                  .with_settings("os"))
    conanfile_require = (GenConanfile().with_package_file("bin/myapp", "myexe")
                                       .with_package_file("lib/mylib", "mylibcontent")
                                       .with_settings("os"))
    if require_run:
        conanfile_require.with_package_type("application")
    client.save({"build_require_pkg/conanfile.py": conanfile_br,
                 "require_pkg/conanfile.py": conanfile_require,
                 "consumer_pkg/conanfile.py": consumer_pkg})

    client.run("export build_require_pkg --name=build_require_pkg --version=1.0")
    client.run("export require_pkg --name=require_pkg --version=1.0")

    client.run("install consumer_pkg --build='*'")
    if platform.system() == "Windows":
        conanbuildenv = client.load("consumer_pkg/conanbuildenv.bat")
        if require_run:
            conanrunenv = client.load("consumer_pkg/conanrunenv.bat")
            assert "LD_LIBRARY_PATH" not in conanbuildenv
            assert "LD_LIBRARY_PATH" not in conanrunenv
        else:
            assert not os.path.exists("consumer_pkg/conanrunenv.bat")
    else:
        if require_run:
            conanbuildenv = client.load("consumer_pkg/conanbuildenv.sh")
            conanrunenv = client.load("consumer_pkg/conanrunenv.sh")
            assert "LD_LIBRARY_PATH" in conanbuildenv
            assert "LD_LIBRARY_PATH" in conanrunenv
        else:
            assert not os.path.exists("consumer_pkg/conanrunenv.sh")

    if require_run:
        # Build context LINUX - Host context LINUX
        client.run("install consumer_pkg -s:b os=Linux -s:h os=Linux --build='*'")
        conanbuildenv = client.load("consumer_pkg/conanbuildenv.sh")
        conanrunenv = client.load("consumer_pkg/conanrunenv.sh")
        assert "LD_LIBRARY_PATH" in conanbuildenv
        assert "LD_LIBRARY_PATH" in conanrunenv

        # Build context WINDOWS - Host context WINDOWS
        client.run("install consumer_pkg -s:b os=Windows -s:h os=Windows --build='*'")
        conanbuildenv = client.load("consumer_pkg/conanbuildenv.bat")
        conanrunenv = client.load("consumer_pkg/conanrunenv.bat")
        assert "LD_LIBRARY_PATH" not in conanbuildenv
        assert "LD_LIBRARY_PATH" not in conanrunenv

        # Build context LINUX - Host context WINDOWS
        client.run("install consumer_pkg -s:b os=Linux -s:h os=Windows --build='*'")
        conanbuildenv = client.load("consumer_pkg/conanbuildenv.sh")
        conanrunenv = client.load("consumer_pkg/conanrunenv.bat")
        assert "LD_LIBRARY_PATH" in conanbuildenv
        assert "LD_LIBRARY_PATH" not in conanrunenv

        # Build context WINDOWS - Host context LINUX
        client.run("install consumer_pkg -s:b os=Windows -s:h os=Linux --build='*'")
        conanbuildenv = client.load("consumer_pkg/conanbuildenv.bat")
        conanrunenv = client.load("consumer_pkg/conanrunenv.sh")
        assert "LD_LIBRARY_PATH" not in conanbuildenv
        assert "LD_LIBRARY_PATH" in conanrunenv


def test_multiple_deactivate():
    conanfile = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.env import Environment
        class Pkg(ConanFile):
            def generate(self):
                e1 = Environment()
                e1.define("VAR1", "Value1")
                e1.vars(self).save_script("mybuild1")
                e2 = Environment()
                e2.define("VAR2", "Value2")
                e2.vars(self).save_script("mybuild2")
        """)
    display_bat = textwrap.dedent("""\
        @echo off
        echo VAR1=%VAR1%!!
        echo VAR2=%VAR2%!!
        """)
    display_sh = textwrap.dedent("""\
        echo VAR1=$VAR1!!
        echo VAR2=$VAR2!!
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "display.bat": display_bat,
                 "display.sh": display_sh})
    os.chmod(os.path.join(client.current_folder, "display.sh"), 0o777)
    client.run("install .")

    for _ in range(2):  # Just repeat it, so we can check things keep working
        if platform.system() == "Windows":
            cmd = "conanbuild.bat && display.bat && deactivate_conanbuild.bat && display.bat"
        else:
            cmd = '. ./conanbuild.sh && ./display.sh && . ./deactivate_conanbuild.sh && ./display.sh'
        out, _ = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  shell=True, cwd=client.current_folder).communicate()
        out = out.decode()
        assert "VAR1=Value1!!" in out
        assert "VAR2=Value2!!" in out
        assert 3 == str(out).count("Restoring environment")
        assert "VAR1=!!" in out
        assert "VAR2=!!" in out


def test_multiple_deactivate_order():
    """
    https://github.com/conan-io/conan/issues/13693
    """
    conanfile = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.env import Environment
        class Pkg(ConanFile):
            def generate(self):
                e1 = Environment()
                e1.define("MYVAR", "Value1")
                e1.vars(self).save_script("mybuild1")
                e2 = Environment()
                e2.define("MYVAR", "Value2")
                e2.vars(self).save_script("mybuild2")
        """)
    display_bat = textwrap.dedent("""\
        @echo off
        echo MYVAR=%MYVAR%!!
        """)
    display_sh = textwrap.dedent("""\
        echo MYVAR=$MYVAR!!
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "display.bat": display_bat,
                 "display.sh": display_sh})
    os.chmod(os.path.join(client.current_folder, "display.sh"), 0o777)
    client.run("install .")

    for _ in range(2):  # Just repeat it, so we can check things keep working
        if platform.system() == "Windows":
            cmd = "conanbuild.bat && display.bat && deactivate_conanbuild.bat && display.bat"
        else:
            cmd = '. ./conanbuild.sh && ./display.sh && . ./deactivate_conanbuild.sh && ./display.sh'
        out, _ = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  shell=True, cwd=client.current_folder).communicate()
        out = out.decode()
        assert "MYVAR=Value2!!" in out
        assert 3 == str(out).count("Restoring environment")
        assert "MYVAR=!!" in out


@pytest.mark.skipif(platform.system() != "Windows", reason="Path problem in Windows only")
@pytest.mark.parametrize("num_deps", [3, ])
def test_massive_paths(num_deps):
    """ This test proves that having too many dependencies that will result in a very long PATH
    env-var in the consumer by one VirtualXXXEnv environment, will overflow.
    https://github.com/conan-io/conan/issues/9565
    This seems an unsolvable limitation, the only alternatives are:
    - shorten the paths in general (shorter cache paths)
    - add exclusively the paths of needed things (better visibility)
    Seems that Conan 2.0 will improve over these things, allowing larger dependencies graphs without
    failing. Besides that, it might use the deployers to workaround shared-libs running scenarios.

    The test is parameterized for being fast an passing, but if we add a num_deps >= 80 approx,
    it will start to enter the failing scenarios. Not adding the >=80 scenario, because that tests
    takes 1 minute by itself, not worth the value.
    """
    client = TestClient(path_with_spaces=False)
    compiler_bat = "@echo off\necho MYTOOL {}!!\n"
    conanfile = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            exports_sources = "*"
            package_type = "application"
            def package(self):
                copy(self, "*", self.build_folder, os.path.join(self.package_folder, "bin"))
        """)

    for i in range(num_deps):
        client.save({"conanfile.py": conanfile,
                     "mycompiler{}.bat".format(i): compiler_bat.format(i)})
        client.run("create . --name=pkg{} --version=0.1".format(i))

    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            requires = {}
            generators = "VirtualRunEnv"
        """)
    requires = ", ".join('"pkg{}/0.1"'.format(i) for i in range(num_deps))
    conanfile = conanfile.format(requires)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -c tools.env.virtualenv:powershell=True")
    assert os.path.isfile(os.path.join(client.current_folder, "conanrunenv.ps1"))
    assert not os.path.isfile(os.path.join(client.current_folder, "conanrunenv.bat"))
    for i in range(num_deps):
        cmd = environment_wrap_command("conanrunenv", client.current_folder,
                                       "mycompiler{}.bat".format(i))
        if num_deps > 50:  # to be safe if we change the "num_deps" number
            client.run_command(cmd, assert_error=True)
            assert "is not recognized as an internal" in client.out
        else:
            client.run_command(cmd)
            assert "MYTOOL {}!!".format(i) in client.out

    # Test .bats now
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install .")
    assert not os.path.isfile(os.path.join(client.current_folder, "conanrunenv.ps1"))
    assert os.path.isfile(os.path.join(client.current_folder, "conanrunenv.bat"))
    for i in range(num_deps):
        cmd = environment_wrap_command("conanrunenv", client.current_folder,
                                       "mycompiler{}.bat".format(i))
        if num_deps > 50:  # to be safe if we change the "num_deps" number
            client.run_command(cmd, assert_error=True)
            # This also fails, but without an error message (in my terminal, it kills the terminal!)
        else:
            client.run_command(cmd)
            assert "MYTOOL {}!!".format(i) in client.out


def test_profile_build_env_spaces():
    display_bat = textwrap.dedent("""\
        @echo off
        echo VAR1=%VAR1%!!
        """)
    display_sh = textwrap.dedent("""\
        echo VAR1=$VAR1!!
        """)
    client = TestClient()
    client.save({"conanfile.txt": "",
                 "profile": "[buildenv]\nVAR1 = VALUE1",
                 "display.bat": display_bat,
                 "display.sh": display_sh})
    os.chmod(os.path.join(client.current_folder, "display.sh"), 0o777)
    client.run("install . -g VirtualBuildEnv -pr=profile")

    if platform.system() == "Windows":
        cmd = "conanbuild.bat && display.bat && deactivate_conanbuild.bat && display.bat"
    else:
        cmd = '. ./conanbuild.sh && ./display.sh && . ./deactivate_conanbuild.sh && ./display.sh'
    out, _ = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              shell=True, cwd=client.current_folder).communicate()
    out = out.decode()
    assert "VAR1= VALUE1!!" in out
    assert "Restoring environment" in out
    assert "VAR1=!!" in out


def test_deactivate_location():
    conanfile = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.env import Environment
        class Pkg(ConanFile):
            def package_info(self):
                self.buildenv_info.define("FOO", "BAR")
        """)
    client = TestClient()
    client.save({"pkg.py": conanfile})
    client.run("create pkg.py --name pkg --version 1.0")
    client.run("install --requires pkg/1.0@ -g VirtualBuildEnv -of=myfolder -s build_type=Release -s arch=x86_64")

    source_cmd, script_ext = ("myfolder\\", ".bat") if platform.system() == "Windows" else (". ./myfolder/", ".sh")
    cmd = "{}conanbuild{}".format(source_cmd, script_ext)

    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,
                     cwd=client.current_folder).communicate()

    assert not os.path.exists(os.path.join(client.current_folder,
                                           "deactivate_conanbuildenv-release-x86_64{}".format(script_ext)))

    assert os.path.exists(os.path.join(client.current_folder, "myfolder",
                                       "deactivate_conanbuildenv-release-x86_64{}".format(script_ext)))


@pytest.mark.skipif(platform.system() == "Windows", reason="Requires sh")
def test_skip_virtualbuildenv_run():
    # Build require
    conanfile = textwrap.dedent(r"""
           from conan import ConanFile
           class Pkg(ConanFile):
               def package_info(self):
                   self.buildenv_info.define("FOO", "BAR")
           """)
    client = TestClient()
    client.save({"pkg.py": conanfile})
    client.run("create pkg.py --name pkg --version 1.0")

    # consumer
    conanfile = textwrap.dedent(r"""
               import os
               from conan import ConanFile
               class Consumer(ConanFile):
                   tool_requires = "pkg/1.0"
                   exports_sources = "my_script.sh"
                   # This can be removed at Conan 2
                   generators = "VirtualBuildEnv"
                   def build(self):
                       path = os.path.join(self.source_folder, "my_script.sh")
                       os.chmod(path, 0o777)
                       self.run("'{}'".format(path))
               """)
    my_script = 'echo FOO is $FOO'
    client.save({"conanfile.py": conanfile, "my_script.sh": my_script})
    client.run("create . --name consumer --version 1.0")
    assert "FOO is BAR" in client.out

    # If we pass env=None no "conanbuild" is applied
    # self.run("'{}'".format(path), env=None)
    conanfile = conanfile.replace(".format(path))",
                                  ".format(path), env=None)")
    client.save({"conanfile.py": conanfile})
    client.run("create . --name consumer --version 1.0")
    assert "FOO is BAR" not in client.out


def test_files_always_created():
    """ test that even if there are no env-variables, the generators always create files,
    they will be mostly empty, but exist
    """
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "consumer/conanfile.txt": "[requires]\ndep/0.1"})
    c.run("create dep")
    c.run("install consumer -g VirtualBuildEnv -g VirtualRunEnv -of=.")
    ext = "bat" if platform.system() == "Windows" else "sh"

    arch = c.get_default_host_profile().settings['arch']
    assert os.path.isfile(os.path.join(c.current_folder, f"conanbuild.{ext}"))
    assert os.path.isfile(os.path.join(c.current_folder, f"conanrun.{ext}"))
    assert os.path.isfile(os.path.join(c.current_folder, f"conanbuildenv-release-{arch}.{ext}"))
    assert os.path.isfile(os.path.join(c.current_folder, f"conanbuildenv-release-{arch}.{ext}"))


def test_error_with_dots_virtualenv():
    # https://github.com/conan-io/conan/issues/12163
    tool = textwrap.dedent(r"""
        from conan import ConanFile
        class ToolConan(ConanFile):
            name = "tool"
            version = "0.1"
            settings = "arch", "os"

            def package_info(self):
                self.buildenv_info.define("DUMMY", "123456")
        """)
    test_package = textwrap.dedent(r"""
        from conan import ConanFile
        import os

        class ToolTestConan(ConanFile):
            name = "app"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "VirtualBuildEnv"

            def build_requirements(self):
                self.tool_requires("tool/0.1")

            def build(self):
                self.run("echo DUMMY=$DUMMY")
                self.run("set")
            """)
    client = TestClient()
    client.save({"dep/conanfile.py": tool,
                 "consumer/conanfile.py": test_package})

    client.run("create dep -s:b arch=armv8.3")
    client.run("create consumer -s arch=armv8.3")
    assert "DUMMY=123456" in client.out


def test_runenv_info_propagated():
    """
    A runenv_info in a recipe, which is required by an executable that is used
    in another place as a tool_require (also its own test_package), should be
    propagated
    test_package --(tool_requires)->tools-(requires)->lib(defines runenv_info)
    https://github.com/conan-io/conan/issues/12939
    """
    c = TestClient()
    # NOTE: The lib contains ``package_type = "shared-library"`` to force propagation of runenv_info
    lib = textwrap.dedent("""
        from conan import ConanFile
        class Lib(ConanFile):
            name = "lib"
            version = "0.1"
            settings = "build_type"
            package_type = "shared-library"
            def package_info(self):
                self.runenv_info.define("MYLIBVAR", f"MYLIBVALUE:{self.settings.build_type}")
        """)
    tool_test_package = textwrap.dedent("""
        import platform
        from conan import ConanFile
        class TestTool(ConanFile):
            settings = "build_type"
            test_type = "explicit"
            generators = "VirtualBuildEnv"
            def build_requirements(self):
                self.tool_requires(self.tested_reference_str)
            def build(self):
                self.output.info(f"Building TEST_PACKAGE IN {self.settings.build_type}!!")
                if platform.system()!= "Windows":
                    self.run("echo MYLIBVAR=$MYLIBVAR")
                else:
                    self.run("set MYLIBVAR")
            def test(self):
                pass
        """)
    c.save({"lib/conanfile.py": lib,
            "tool/conanfile.py": GenConanfile("tool", "0.1").with_requires("lib/0.1"),
            "tool/test_package/conanfile.py": tool_test_package})
    c.run("create lib -s build_type=Release")
    c.run("create tool --build-require -s:b build_type=Release -s:h build_type=Debug")
    assert "tool/0.1 (test package): Building TEST_PACKAGE IN Debug!!" in c.out
    assert "MYLIBVAR=MYLIBVALUE:Release" in c.out


def test_deactivate_relocatable_substitute():
    c = TestClient()
    # this cannot be tested in CI, because permissions over root folder
    # c.current_folder = "/build"
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("install . -s os=Linux -s:b os=Linux")
    conanbuild = c.load("conanbuildenv.sh")
    result = os.path.join("$script_folder", "deactivate_conanbuildenv.sh")
    assert f'"{result}"' in conanbuild
