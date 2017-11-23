import os
import platform
import shutil
import sys


def get_tox_ini():
    tox_template = """
[tox]
envlist = py27,py347,py36

[testenv]
setenv = MYENV = 2
passenv = *

deps = -rconans/requirements.txt
       -rconans/requirements_dev.txt
       -rconans/requirements_server.txt
commands=nosetests {posargs: conans/test}  --verbosity=3 --processes=4 --process-timeout=1000
"""

    tox_win = """ 
[testenv:py27] 
basepython=C:\Python27\python.exe

[testenv:py347] 
basepython=C:\Python34\python.exe

[testenv:py36] 
basepython=C:\Python36\python.exe

"""
    tox_macos = """ """
    tox_linux = """ """

    return tox_template + {"Windows": tox_win,
                           "Darwin": tox_macos,
                           "Linux": tox_linux}.get(platform.system())


def get_command(pyver):
    command = "tox -e py%s" % pyver
    if platform.system() == "Linux":
        command = 'docker run --rm -v$(pwd):/home/conan/ lasote/conantests bash -c "%s"' % command
    return command

if __name__ == "__main__":

    print(os.environ)

    with open("tox.ini", "w") as file:
        file.write(get_tox_ini())

    if os.getenv("JENKINS_HOME", None):
        shutil.rmtree(".git")  # Clean the repo, save space
    pyver = os.getenv("pyver", None)
    os.system("pip install tox --upgrade")

    command = get_command(pyver)
    print("RUNNING: %s" % command)
    ret = os.system(command)
    sys.exit(ret)
 
