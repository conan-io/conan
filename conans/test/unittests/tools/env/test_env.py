import subprocess
import textwrap

from conan.tools.env import Environment
from conan.tools.env.environment import EnvironmentItem
from conans.client.tools import chdir
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_basic_serialize():
    env = Environment()
    env["MyVar"].define("MyValue")
    text = env.dumps()


def test_compose():
    env = Environment()
    env["MyVar"].define("MyValue")
    env["MyVar2"].define("MyValue2")
    env["MyVar3"].define("MyValue3")
    env["MyVar4"].define("MyValue4")

    env2 = Environment()
    env2["MyVar"].define("MyNewValue")
    env2["MyVar2"].append("MyNewValue2")
    env2["MyVar3"].prepend("MyNewValue3")
    env2["MyVar4"].clean()

    env3 = env.compose(env2)
    assert env3["MyVar"].value == ["MyNewValue"]
    assert env3["MyVar"].action == EnvironmentItem.DEFINE
    assert env3["MyVar2"].value == ['MyValue2', 'MyNewValue2']
    assert env3["MyVar2"].action == EnvironmentItem.DEFINE
    assert env3["MyVar3"].value == ['MyNewValue3', 'MyValue3']
    assert env3["MyVar3"].action == EnvironmentItem.DEFINE
    assert env3["MyVar4"].action == EnvironmentItem.CLEAN


def test_bat():
    env = Environment()
    env["MyVar"].define("MyValue")
    env["MyVar1"].define("MyValue1")
    env["MyVar2"].append("MyValue2")
    env["MyVar3"].prepend("MyValue3")
    env["MyVar4"].clean()
    folder = temp_folder()
    with chdir(folder):
        env.save_bat("test.bat")

        save("display.bat", textwrap.dedent("""\
            @echo off
            echo MyVar=%MyVar%!!
            echo MyVar1=%MyVar1%!!
            echo MyVar2=%MyVar2%!!
            echo MyVar3=%MyVar3%!!
            echo MyVar4=%MyVar4%!!
            """))
        cmd = "test.bat && display.bat && deactivate_test.bat && display.bat"
        prevenv = {"MyVar1": "OldVar1",
                   "MyVar2": "OldVar2",
                   "MyVar3": "OldVar3",
                   "MyVar4": "OldVar4"}
        out, _ = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                  env=prevenv, shell=True).communicate()
        out = out.decode()
        assert "MyVar=MyValue!!" in out
        assert "MyVar1=MyValue1!!" in out
        assert "MyVar2=OldVar2 MyValue2!!" in out
        assert "MyVar3=MyValue3 OldVar3!!" in out
        assert "MyVar4=!!" in out

        assert "MyVar=!!" in out
        assert "MyVar1=OldVar1!!" in out
        assert "MyVar2=OldVar2!!" in out
        assert "MyVar3=OldVar3!!" in out
        assert "MyVar4=OldVar4!!" in out
