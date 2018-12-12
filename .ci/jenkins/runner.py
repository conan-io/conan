import os
import platform

from conf import Extender, chdir, environment_append, get_environ, linuxpylocation, \
    macpylocation, winpylocation, win_msbuilds_logs_folder

from gh_pr_reader import get_tag_from_pr


pylocations = {"Windows": winpylocation,
               "Linux": linuxpylocation,
               "Darwin": macpylocation}[platform.system()]


def get_tag_argument_value(branch):
    """Reading the pull request body, decide which tags apply to nosetests"""
    if not branch.startswith("PR-"):
        return '' # By default all the branches runs all
    pr_number = branch.split("PR-")[1]
    line = get_tag_from_pr(int(pr_number), "CI:")
    if line is None: # By default
        return '-A "not slow"'
    # If the tag is specify use it, if not, by default run only the not slow
    return '-A "%s"' % line if line else ""


def run_tests(module_path, pyver, source_folder, tmp_folder, flavor, branch_name,
              num_cores=3, verbosity=None):

    verbosity = verbosity or (2 if platform.system() == "Windows" else 1)
    venv_dest = os.path.join(tmp_folder, "venv")
    if not os.path.exists(venv_dest):
        os.makedirs(venv_dest)
    venv_exe = os.path.join(venv_dest,
                            "bin" if platform.system() != "Windows" else "Scripts",
                            "activate")
    tags_argument = get_tag_argument_value(branch_name)
    pyenv = pylocations[pyver]
    source_cmd = "." if platform.system() != "Windows" else ""
    # Prevent OSX to lock when no output is received
    debug_traces = ""  # "--debug=nose,nose.result" if platform.system() == "Darwin" and pyver != "py27" else ""
    # pyenv = "/usr/local/bin/python2"
    multiprocess = ("--processes=%s --process-timeout=1000 "
                    "--process-restartworker --with-coverage" % num_cores) if platform.system() != "Darwin" else ""

    if num_cores <= 1:
        multiprocess = ""

    pip_installs = "pip install -r conans/requirements.txt && " \
                   "pip install -r conans/requirements_dev.txt && " \
                   "pip install -r conans/requirements_server.txt && "

    if platform.system() == "Darwin":
        pip_installs += "pip install -r conans/requirements_osx.txt && "

    #  --nocapture
    command = "virtualenv --python \"{pyenv}\" \"{venv_dest}\" && " \
              "{source_cmd} \"{venv_exe}\" && " \
              "{pip_installs} " \
              "python setup.py install && " \
              "conan --version && conan --help && " \
              "nosetests {module_path} {tags_argument} --verbosity={verbosity} " \
              "{multiprocess} " \
              "{debug_traces} " \
              "--with-xunit " \
              "&& codecov -t f1a9c517-3d81-4213-9f51-61513111fc28".format(
                                    **{"module_path": module_path,
                                       "pyenv": pyenv,
                                       "tags_argument": tags_argument,
                                       "venv_dest": venv_dest,
                                       "verbosity": verbosity,
                                       "venv_exe": venv_exe,
                                       "source_cmd": source_cmd,
                                       "debug_traces": debug_traces,
                                       "multiprocess": multiprocess,
                                       "pip_installs": pip_installs})

    env = get_environ(tmp_folder)
    env["PYTHONPATH"] = source_folder
    env["CONAN_LOGGING_LEVEL"] = "50" if platform.system() == "Darwin" else "50"
    env["CHANGE_AUTHOR_DISPLAY_NAME"] = ""
    env["CONAN_API_V2_BLOCKED"] = "True" if flavor == "blocked_v2" else "False"
    env["CONAN_CLIENT_REVISIONS_ENABLED"] = "True" if flavor == "enabled_revisions" else "False"
    env["GH_TOKEN"] = ""  # Security, clear the token
    # Try to specify a known folder to keep there msbuild failure logs
    env["MSBUILDDEBUGPATH"] = win_msbuilds_logs_folder

    with chdir(source_folder):
        if os.path.exists("setup.cfg"):
            os.rename("setup.cfg", "setup.cfg_INVALID")  # Do not use default test launch
        with environment_append(env):
            run(command)


def run(command):
    print("--CALLING: %s" % command)
    # return os.system(command)
    import subprocess

    # ret = subprocess.call("bash -c '%s'" % command, shell=True)
    shell = '/bin/bash' if platform.system() != "Windows" else None
    ret = subprocess.call(command, shell=True, executable=shell)
    if ret != 0:
        raise Exception("Error running: '%s'" % command)


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description='Launch tests in a venv')
    parser.add_argument('module', help='e.g.: conans.test')
    parser.add_argument('pyver', help='e.g.: py27')
    parser.add_argument('source_folder', help='Folder containing the conan source code')
    parser.add_argument('tmp_folder', help='Folder to create the venv inside')
    parser.add_argument('--num_cores', type=int, help='Number of cores to use', default=3)
    parser.add_argument('--flavor', '-f', help='enabled_revisions, disabled_revisions, blocked_v2')
    parser.add_argument('--branch', '-b', help='branch being built. PR-XXX for PRs')
    args = parser.parse_args()

    run_tests(args.module, args.pyver, args.source_folder, args.tmp_folder, args.flavor,
              args.branch, num_cores=args.num_cores)
