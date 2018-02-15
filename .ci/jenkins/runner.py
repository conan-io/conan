import os

from conf import winpylocation, linuxpylocation, macpylocation, Extender, environment_append, chdir, get_environ
import platform


pylocations = {"Windows": winpylocation,
               "Linux": linuxpylocation,
               "Darwin": macpylocation}[platform.system()]


def run_tests(module_path, pyver, source_folder, tmp_folder,
              exluded_tags, num_cores=3, verbosity=None):

    verbosity = verbosity or (2 if platform.system() == "Windows" else 1)
    exluded_tags = exluded_tags or ""
    venv_dest = os.path.join(tmp_folder, "venv")
    if not os.path.exists(venv_dest):
        os.makedirs(venv_dest)
    venv_exe = os.path.join(venv_dest,
                            "bin" if platform.system() != "Windows" else "Scripts",
                            "activate")
    if exluded_tags:
        exluded_tags = '-A "%s"' % " and ".join(["not %s" % tag for tag in exluded_tags])

    pyenv = pylocations[pyver]
    source_cmd = "." if platform.system() != "Windows" else ""
    # Prevent OSX to lock when no output is received
    debug_traces = ""  # "--debug=nose,nose.result" if platform.system() == "Darwin" and pyver != "py27" else ""
    # pyenv = "/usr/local/bin/python2"
    multiprocess = ("--processes=%s --process-timeout=1000 "
                    "--process-restartworker --with-coverage" % num_cores) if platform.system() != "Darwin" or pyver == "py27" else ""

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
              "nosetests {module_path} {excluded_tags} --verbosity={verbosity} " \
              "{multiprocess} " \
              "{debug_traces} " \
              "--with-xunit " \
              "&& codecov -t f1a9c517-3d81-4213-9f51-61513111fc28".format(
                                    **{"module_path": module_path,
                                       "pyenv": pyenv,
                                       "excluded_tags": exluded_tags,
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
    with chdir(source_folder):
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
    parser.add_argument('module', help='e.j: conans.test')
    parser.add_argument('pyver', help='e.j: py27')
    parser.add_argument('source_folder', help='Folder containing the conan source code')
    parser.add_argument('tmp_folder', help='Folder to create the venv inside')
    parser.add_argument('--num_cores', type=int, help='Number of cores to use', default=3)
    parser.add_argument('--exclude_tag', '-e', nargs=1, action=Extender,
                        help='Tags to exclude from testing, e.j: rest_api')

    args = parser.parse_args()
    run_tests(args.module, args.pyver, args.source_folder, args.tmp_folder, args.exclude_tag, num_cores=args.num_cores)

