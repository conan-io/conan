import os

from conf import winpylocation, linuxpylocation, macpylocation, Extender, environment_append, chdir, get_environ
import platform


pylocations = {"Windows": winpylocation,
               "Linux": linuxpylocation,
               "Darwin": macpylocation}[platform.system()]


def run_tests(module_path, pyver, source_folder, tmp_folder, flavor,
              excluded_tags, num_cores=3, verbosity=None, server_api=None):

    verbosity = verbosity or (2 if platform.system() == "Windows" else 1)
    venv_dest = os.path.join(tmp_folder, "venv")
    if not os.path.exists(venv_dest):
        os.makedirs(venv_dest)
    venv_exe = os.path.join(venv_dest,
                            "bin" if platform.system() != "Windows" else "Scripts",
                            "activate")

    if flavor == "revisions":
        excluded_tags.append("only_without_revisions")
    elif flavor == "no_revisions":
        excluded_tags.append("only_revisions")

    exluded_tags_str = '-A "%s"' % " and ".join(["not %s" % tag for tag in excluded_tags]) if excluded_tags else ""

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
                                       "excluded_tags": exluded_tags_str,
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
    if server_api == "v2":
        env["CONAN_TESTING_SERVER_V2_ENABLED"] = "1"
    if flavor == "revisions":
        env["CONAN_TESTING_SERVER_REVISIONS_ENABLED"] = "1"

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
    parser.add_argument('module', help='e.g.: conans.test')
    parser.add_argument('pyver', help='e.g.: py27')
    parser.add_argument('source_folder', help='Folder containing the conan source code')
    parser.add_argument('tmp_folder', help='Folder to create the venv inside')
    parser.add_argument('--num_cores', type=int, help='Number of cores to use', default=3)
    parser.add_argument('--server_api', help='Test all with v1 or v2', default="v1")
    parser.add_argument('--exclude_tag', '-e', nargs=1, action=Extender,
                        help='Tags to exclude from testing, e.g.: rest_api')
    parser.add_argument('--flavor', '-f', help='Flavor (revisions, no_revisions)')

    args = parser.parse_args()

    run_tests(args.module, args.pyver, args.source_folder, args.tmp_folder, args.flavor,
              args.exclude_tag, num_cores=args.num_cores, server_api=args.server_api)
