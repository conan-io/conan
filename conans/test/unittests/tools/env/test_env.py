import os
import platform
import subprocess
import textwrap

import pytest

from conan.tools.env import Environment
from conan.tools.env.environment import ProfileEnvironment
from conans.client.tools import chdir
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_compose():
    env = Environment()
    env.define("MyVar", "MyValue")
    env.define("MyVar2", "MyValue2")
    env.define("MyVar3", "MyValue3")
    env.define("MyVar4", "MyValue4")
    env.unset("MyVar5")

    env2 = Environment()
    env2.define("MyVar", "MyNewValue")
    env2.append("MyVar2", "MyNewValue2")
    env2.prepend("MyVar3", "MyNewValue3")
    env2.unset("MyVar4")
    env2.define("MyVar5", "MyNewValue5")

    env.compose(env2)
    assert env.value("MyVar") == "MyNewValue"
    assert env.value("MyVar2") == 'MyValue2 MyNewValue2'
    assert env.value("MyVar3") == 'MyNewValue3 MyValue3'
    assert env.value("MyVar4") == ""
    assert env.value("MyVar5") == 'MyNewValue5'


@pytest.mark.parametrize("op1, v1, s1, op2, v2, s2, result",
                         [("define", "Val1", " ", "define", "Val2", " ", "Val2"),
                          ("define", "Val1", " ", "append", "Val2", " ", "Val1 Val2"),
                          ("define", "Val1", " ", "prepend", "Val2", " ", "Val2 Val1"),
                          ("define", "Val1", " ", "unset", "", " ", ""),
                          ("append", "Val1", " ", "define", "Val2", " ", "Val2"),
                          ("append", "Val1", " ", "append", "Val2", " ", "MyVar Val1 Val2"),
                          ("append", "Val1", " ", "prepend", "Val2", " ", "Val2 MyVar Val1"),
                          ("append", "Val1", " ", "unset", "", " ", ""),
                          ("prepend", "Val1", " ", "define", "Val2", " ", "Val2"),
                          ("prepend", "Val1", " ", "append", "Val2", " ", "Val1 MyVar Val2"),
                          ("prepend", "Val1", " ", "prepend", "Val2", " ", "Val2 Val1 MyVar"),
                          ("prepend", "Val1", " ", "unset", "", " ", ""),
                          ("unset", "", " ", "define", "Val2", " ", "Val2"),
                          ("unset", "", " ", "append", "Val2", " ", "Val2"),
                          ("unset", "", " ", "prepend", "Val2", " ", "Val2"),
                          ("unset", "", " ", "unset", "", " ", ""),
                          # different separators
                          ("append", "Val1", "+", "append", "Val2", "-", "MyVar+Val1-Val2"),
                          ("append", "Val1", "+", "prepend", "Val2", "-", "Val2-MyVar+Val1"),
                          ("unset", "", " ", "append", "Val2", "+", "Val2"),
                          ("unset", "", " ", "prepend", "Val2", "+", "Val2"),
                          ])
def test_compose_combinations(op1, v1, s1, op2, v2, s2, result):
    env = Environment()
    if op1 != "unset":
        getattr(env, op1)("MyVar", v1, s1)
    else:
        env.unset("MyVar")
    env2 = Environment()
    if op2 != "unset":
        getattr(env2, op2)("MyVar", v2, s2)
    else:
        env2.unset("MyVar")
    env.compose(env2)
    assert env.value("MyVar") == result


@pytest.mark.parametrize("op1, v1, op2, v2, result",
                         [("define", "/path1", "define", "/path2", "/path2"),
                          ("define", "/path1", "append", "/path2", "/path1:/path2"),
                          ("define", "/path1", "prepend", "/path2", "/path2:/path1"),
                          ("define", "/path1", "unset", "", ""),
                          ("append", "/path1", "define", "/path2", "/path2"),
                          ("append", "/path1", "append", "/path2", "MyVar:/path1:/path2"),
                          ("append", "/path1", "prepend", "/path2", "/path2:MyVar:/path1"),
                          ("append", "/path1", "unset", "", ""),
                          ("prepend", "/path1", "define", "/path2", "/path2"),
                          ("prepend", "/path1", "append", "/path2", "/path1:MyVar:/path2"),
                          ("prepend", "/path1", "prepend", "/path2", "/path2:/path1:MyVar"),
                          ("prepend", "/path1", "unset", "", ""),
                          ("unset", "", "define", "/path2", "/path2"),
                          ("unset", "", "append", "/path2", "/path2"),
                          ("unset", "", "prepend", "/path2", "/path2"),
                          ("unset", "", "unset", "", ""),
                          ])
def test_compose_path_combinations(op1, v1, op2, v2, result):
    env = Environment()
    if op1 != "unset":
        getattr(env, op1+"_path")("MyVar", v1)
    else:
        env.unset("MyVar")
    env2 = Environment()
    if op2 != "unset":
        getattr(env2, op2+"_path")("MyVar", v2)
    else:
        env2.unset("MyVar")
    env.compose(env2)
    assert env.value("MyVar", pathsep=":") == result


def test_profile():
    myprofile = textwrap.dedent("""
        # define
        MyVar1=MyValue1
        #  append
        MyVar2+=MyValue2
        #  multiple append works
        MyVar2+=MyValue2_2
        #  prepend
        MyVar3=+MyValue3
        # unset
        MyVar4=!
        # Empty
        MyVar5=

        # PATHS
        # define
        MyPath1=(path)/my/path1
        #  append
        MyPath2+=(path)/my/path2
        #  multiple append works
        MyPath2+=(path)/my/path2_2
        #  prepend
        MyPath3=+(path)/my/path3
        # unset
        MyPath4=!

        # PER-PACKAGE
        mypkg*:MyVar2=MyValue2
        """)

    profile_env = ProfileEnvironment()
    profile_env.loads(myprofile)
    env = profile_env.get_env("")
    assert env.value("MyVar1") == "MyValue1"
    assert env.value("MyVar2", "$MyVar2") == '$MyVar2 MyValue2 MyValue2_2'
    assert env.value("MyVar3", "$MyVar3") == 'MyValue3 $MyVar3'
    assert env.value("MyVar4") == ""
    assert env.value("MyVar5") == ''

    env = profile_env.get_env("mypkg1/1.0")
    assert env.value("MyVar1") == "MyValue1"
    assert env.value("MyVar2", "$MyVar2") == 'MyValue2'


def test_env_files():
    env = Environment()
    env.define("MyVar", "MyValue")
    env.define("MyVar1", "MyValue1")
    env.append("MyVar2", "MyValue2")
    env.prepend("MyVar3", "MyValue3")
    env.unset("MyVar4")
    env.define("MyVar5", "MyValue5 With Space5=More Space5;:More")
    env.append("MyVar6", "MyValue6")  # Append, but previous not existing
    env.define_path("MyPath1", "/Some/Path1/")
    env.append_path("MyPath2", ["/Some/Path2/", "/Other/Path2/"])
    env.prepend_path("MyPath3", "/Some/Path3/")
    env.unset("MyPath4")
    folder = temp_folder()

    prevenv = {"MyVar1": "OldVar1",
               "MyVar2": "OldVar2",
               "MyVar3": "OldVar3",
               "MyVar4": "OldVar4",
               "MyPath1": "OldPath1",
               "MyPath2": "OldPath2",
               "MyPath3": "OldPath3",
               "MyPath4": "OldPath4",
               }

    display_bat = textwrap.dedent("""\
        @echo off
        echo MyVar=%MyVar%!!
        echo MyVar1=%MyVar1%!!
        echo MyVar2=%MyVar2%!!
        echo MyVar3=%MyVar3%!!
        echo MyVar4=%MyVar4%!!
        echo MyVar5=%MyVar5%!!
        echo MyVar6=%MyVar6%!!
        echo MyPath1=%MyPath1%!!
        echo MyPath2=%MyPath2%!!
        echo MyPath3=%MyPath3%!!
        echo MyPath4=%MyPath4%!!
        """)

    display_sh = textwrap.dedent("""\
        echo MyVar=$MyVar!!
        echo MyVar1=$MyVar1!!
        echo MyVar2=$MyVar2!!
        echo MyVar3=$MyVar3!!
        echo MyVar4=$MyVar4!!
        echo MyVar5=$MyVar5!!
        echo MyVar6=$MyVar6!!
        echo MyPath1=$MyPath1!!
        echo MyPath2=$MyPath2!!
        echo MyPath3=$MyPath3!!
        echo MyPath4=$MyPath4!!
        """)

    def check(cmd_):
        out, _ = subprocess.Popen(cmd_, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  env=prevenv, shell=True).communicate()
        out = out.decode()
        assert "MyVar=MyValue!!" in out
        assert "MyVar1=MyValue1!!" in out
        assert "MyVar2=OldVar2 MyValue2!!" in out
        assert "MyVar3=MyValue3 OldVar3!!" in out
        assert "MyVar4=!!" in out
        assert "MyVar5=MyValue5 With Space5=More Space5;:More!!" in out
        assert "MyVar6= MyValue6!!" in out  # The previous is non existing, append has space
        assert "MyPath1=/Some/Path1/!!" in out
        assert "MyPath2=OldPath2:/Some/Path2/:/Other/Path2/!!" in out
        assert "MyPath3=/Some/Path3/:OldPath3!!" in out
        assert "MyPath4=!!" in out

        # This should be output when deactivated
        assert "MyVar=!!" in out
        assert "MyVar1=OldVar1!!" in out
        assert "MyVar2=OldVar2!!" in out
        assert "MyVar3=OldVar3!!" in out
        assert "MyVar4=OldVar4!!" in out
        assert "MyVar5=!!" in out
        assert "MyVar6=!!" in out
        assert "MyPath1=OldPath1!!" in out
        assert "MyPath2=OldPath2!!" in out
        assert "MyPath3=OldPath3!!" in out
        assert "MyPath4=OldPath4!!" in out

    with chdir(folder):
        if platform.system() == "Windows":
            env.save_bat("test.bat", pathsep=":")
            save("display.bat", display_bat)
            cmd = "test.bat && display.bat && deactivate_test.bat && display.bat"
            check(cmd)
            # FIXME: Powershell still not working
            # env.save_ps1("test.ps1", pathsep=":")
            # print(load("test.ps1"))
            # cmd = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
            # check(cmd)
        else:
            env.save_sh("test.sh")
            save("display.sh", display_sh)
            os.chmod("display.sh", 0o777)
            cmd = 'bash -c ". test.sh && ./display.sh && . deactivate_test.sh && ./display.sh"'
            check(cmd)


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_windows_case_insensitive():
    # Append and define operation over the same variable in Windows preserve order
    env = Environment()
    env.define("MyVar", "MyValueA")
    env.define("MYVAR", "MyValueB")
    env.define("MyVar1", "MyValue1A")
    env.append("MYVAR1", "MyValue1B")
    folder = temp_folder()

    display_bat = textwrap.dedent("""\
        @echo off
        echo MyVar=%MyVar%!!
        echo MyVar1=%MyVar1%!!
        """)

    with chdir(folder):
        env.save_bat("test.bat")
        save("display.bat", display_bat)
        cmd = "test.bat && display.bat && deactivate_test.bat && display.bat"
        out, _ = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  shell=True).communicate()

    out = out.decode()
    assert "MyVar=MyValueB!!" in out
    assert "MyVar=!!" in out
    assert "MyVar1=MyValue1A MyValue1B!!" in out
    assert "MyVar1=!!" in out
