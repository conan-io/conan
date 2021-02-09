import platform
import subprocess
import textwrap

import pytest

from conan.tools.env import Environment
from conans.client.tools import chdir
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_compose():
    env = Environment()
    env["MyVar"].define("MyValue")
    env["MyVar2"].define("MyValue2")
    env["MyVar3"].define("MyValue3")
    env["MyVar4"].define("MyValue4")
    env["MyVar5"].clean()

    env2 = Environment()
    env2["MyVar"].define("MyNewValue")
    env2["MyVar2"].append("MyNewValue2")
    env2["MyVar3"].prepend("MyNewValue3")
    env2["MyVar4"].clean()
    env2["MyVar5"].define("MyNewValue5")

    env3 = env.compose(env2)
    assert env3["MyVar"].str_value() == "MyNewValue"
    assert env3["MyVar2"].str_value() == 'MyValue2 MyNewValue2'
    assert env3["MyVar3"].str_value() == 'MyNewValue3 MyValue3'
    assert env3["MyVar4"].str_value() == ""
    assert env3["MyVar5"].str_value() == 'MyNewValue5'


def test_env_files():
    env = Environment()
    env["MyVar"].define("MyValue")
    env["MyVar1"].define("MyValue1")
    env["MyVar2"].append("MyValue2")
    env["MyVar3"].prepend("MyValue3")
    env["MyVar4"].clean()
    env["MyVar5"].define("MyValue5 With Space5=More Space5;:More")
    env["MyPath1"].define_path("/Some/Path1/")
    env["MyPath2"].append_path(["/Some/Path2/", "/Other/Path2/"])
    env["MyPath3"].prepend_path("/Some/Path3/")
    env["MyPath4"].clean()
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
        echo MyPath1=$MyPath1!!
        echo MyPath2=$MyPath2!!
        echo MyPath3=$MyPath3!!
        echo MyPath4=$MyPath4!!
        """)

    with chdir(folder):
        if platform.system() == "Windows":
            env.save_bat("test.bat", pathsep=":")
            save("display.bat", display_bat)
            cmd = "test.bat && display.bat && deactivate_test.bat && display.bat"

            exe = None
        else:
            env.save_sh("test.sh")
            save("display.sh", display_sh)
            cmd = ". test.sh && . display.sh && . deactivate_test.sh && . display.sh"

            exe = "/bin/bash"
        out, _ = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  env=prevenv, shell=True, executable=exe).communicate()

    out = out.decode()
    assert "MyVar=MyValue!!" in out
    assert "MyVar1=MyValue1!!" in out
    assert "MyVar2=OldVar2 MyValue2!!" in out
    assert "MyVar3=MyValue3 OldVar3!!" in out
    assert "MyVar4=!!" in out
    assert "MyVar5=MyValue5 With Space5=More Space5;:More!!" in out
    assert "MyVar=MyValue!!" in out
    assert "MyPath1=/Some/Path1/!!" in out
    assert "MyPath2=OldPath2:/Some/Path2/:/Other/Path2/!!" in out
    assert "MyPath3=/Some/Path3/:OldPath3!!" in out
    assert "MyPath4=!!" in out

    assert "MyVar=!!" in out
    assert "MyVar1=OldVar1!!" in out
    assert "MyVar2=OldVar2!!" in out
    assert "MyVar3=OldVar3!!" in out
    assert "MyVar4=OldVar4!!" in out
    assert "MyVar5=!!" in out
    assert "MyPath1=OldPath1!!" in out
    assert "MyPath2=OldPath2!!" in out
    assert "MyPath3=OldPath3!!" in out
    assert "MyPath4=OldPath4!!" in out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_windows_case_insensitive():
    # Append and define operation over the same variable in Windows preserve order
    env = Environment()
    env["MyVar"].define("MyValueA")
    env["MYVAR"].define("MyValueB")
    env["MyVar1"].define("MyValue1A")
    env["MYVAR1"].append("MyValue1B")
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
