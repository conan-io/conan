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


def info():
    print("Commit: %s" % os.getenv("GWBT_COMMIT_BEFORE"))
    print("Ref: %s" % os.getenv("GWBT_REF"))
    print("Branch: %s" % os.getenv("GWBT_BRANCH"))
    print("Repo full name: %s" % os.getenv("GWBT_REPO_FULL_NAME"))


def prepare():
    if not os.getenv("$GWBT_COMMIT_AFTER", None):
        print("ERROR: Builds only fired by github")
        raise Exception()
    if not os.getenv("GWBT_BRANCH", None):
        print("ERROR: A branch is needed")
        raise Exception()

    branch = os.getenv("GWBT_BRANCH")
    commit = os.getenv("GWBT_COMMIT_AFTER")
    if not branch:
        raise Exception("Not a branch!")
    if os.path.exists(os.getenv("GWBT_REPO_NAME")):
        shutil.rmtree(os.getenv("GWBT_REPO_NAME"))
    os.system("git clone --single-branch --branch %s https://github.com/${GWBT_REPO_FULL_NAME}.git")
    os.system("git reset --hard %s" % commit)


def get_command(pyver):
    command = "tox -e py%s" % pyver
    if platform.system() == "Linux":
        command = 'docker run --rm -v$(pwd):/home/conan/ lasote/conantests bash -c "%s"' % command
    return command

if __name__ == "__main__":

    info()
    prepare()

    with open("tox.ini", "w") as file:
        file.write(get_tox_ini())

    pyver = os.getenv("pyver", None)
    os.system("pip install tox --upgrade")

    command = get_command(pyver)
    print("RUNNING: %s" % command)
    ret = os.system(command)
    sys.exit(ret)
