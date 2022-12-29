import os
import platform
import subprocess
import textwrap

import pytest

from conan.tools.env import Environment
from conans.client.tools import chdir
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


@pytest.fixture
def env():
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
    return env


@pytest.fixture
def prevenv():
    return {
        "MyVar1": "OldVar1",
        "MyVar2": "OldVar2",
        "MyVar3": "OldVar3 with spaces",
        "MyVar4": "OldVar4 with (some) special @ characters",
        "MyPath1": "OldPath1",
        "MyPath2": "OldPath2",
        "MyPath3": "OldPath3",
        "MyPath4": "OldPath4",
    }


def check_env_files_output(cmd_, prevenv):
    result, _ = subprocess.Popen(cmd_, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=prevenv, shell=True).communicate()
    out = result.decode()

    assert "MyVar=MyValue!!" in out
    assert "MyVar1=MyValue1!!" in out
    assert "MyVar2=OldVar2 MyValue2!!" in out
    assert "MyVar3=MyValue3 OldVar3 with spaces!!" in out
    assert "MyVar4=!!" in out
    assert "MyVar5=MyValue5 With Space5=More Space5;:More!!" in out
    assert "MyVar6= MyValue6!!" in out  # The previous is non existing, append has space
    assert "MyPath1=/Some/Path1/!!" in out
    assert os.pathsep.join(["MyPath2=OldPath2", "/Some/Path2/", "/Other/Path2/!!"]) in out
    assert os.pathsep.join(["MyPath3=/Some/Path3/", "OldPath3!!"]) in out
    assert "MyPath4=!!" in out

    # This should be output when deactivated
    assert "MyVar=!!" in out
    assert "MyVar1=OldVar1!!" in out
    assert "MyVar2=OldVar2!!" in out
    assert "MyVar3=OldVar3 with spaces!!" in out
    assert "MyVar4=OldVar4 with (some) special @ characters!!" in out
    assert "MyVar5=!!" in out
    assert "MyVar6=!!" in out
    assert "MyPath1=OldPath1!!" in out
    assert "MyPath2=OldPath2!!" in out
    assert "MyPath3=OldPath3!!" in out
    assert "MyPath4=OldPath4!!" in out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_env_files_bat(env, prevenv):
    display = textwrap.dedent("""\
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
    t = temp_folder()
    with chdir(t):
        env = env.vars(ConanFileMock())
        env.save_bat("test.bat")
        save("display.bat", display)
        cmd = "test.bat && display.bat && deactivate_test.bat && display.bat"
        check_env_files_output(cmd, prevenv)


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_env_files_ps1(env, prevenv):
    prevenv.update(dict(os.environ.copy()))

    display = textwrap.dedent("""\
        echo "MyVar=$env:MyVar!!"
        echo "MyVar1=$env:MyVar1!!"
        echo "MyVar2=$env:MyVar2!!"
        echo "MyVar3=$env:MyVar3!!"
        echo "MyVar4=$env:MyVar4!!"
        echo "MyVar5=$env:MyVar5!!"
        echo "MyVar6=$env:MyVar6!!"
        echo "MyPath1=$env:MyPath1!!"
        echo "MyPath2=$env:MyPath2!!"
        echo "MyPath3=$env:MyPath3!!"
        echo "MyPath4=$env:MyPath4!!"
    """)

    with chdir(temp_folder()):
        env = env.vars(ConanFileMock())
        env.save_ps1("test.ps1")
        save("display.ps1", display)
        cmd = "powershell.exe .\\test.ps1 ; .\\display.ps1 ; .\\deactivate_test.ps1 ; .\\display.ps1"
        check_env_files_output(cmd, prevenv)


@pytest.mark.skipif(platform.system() == "Windows", reason="Not in Windows")
def test_env_files_sh(env, prevenv):
    display = textwrap.dedent("""\
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

    with chdir(temp_folder()):
        env = env.vars(ConanFileMock())
        env.save_sh("test.sh")
        save("display.sh", display)
        os.chmod("display.sh", 0o777)
        # We include the "set -e" to test it is robust against errors
        cmd = 'set -e && . ./test.sh && ./display.sh && . ./deactivate_test.sh && ./display.sh'
        check_env_files_output(cmd, prevenv)
