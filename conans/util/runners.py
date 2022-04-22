import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager

import six

from conans.client.tools.files import load
from conans.errors import CalledProcessErrorWithStderr
from conans.util.files import rmdir
from conans.util.log import logger


if getattr(sys, 'frozen', False) and 'LD_LIBRARY_PATH' in os.environ:

    # http://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
    pyinstaller_bundle_dir = os.environ['LD_LIBRARY_PATH'].replace(
        os.environ.get('LD_LIBRARY_PATH_ORIG', ''), ''
    ).strip(';:')

    @contextmanager
    def pyinstaller_bundle_env_cleaned():
        """Removes the pyinstaller bundle directory from LD_LIBRARY_PATH

        :return: None
        """
        ld_library_path = os.environ['LD_LIBRARY_PATH']
        os.environ['LD_LIBRARY_PATH'] = ld_library_path.replace(pyinstaller_bundle_dir,
                                                                '').strip(';:')
        yield
        os.environ['LD_LIBRARY_PATH'] = ld_library_path

else:
    @contextmanager
    def pyinstaller_bundle_env_cleaned():
        yield


def version_runner(cmd, shell=False):
    # Used by build helpers like CMake and Meson and MSBuild to get the version
    out, _ = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=shell).communicate()
    return out


def muted_runner(cmd, folder=None):
    # Used by tools/scm check_repo only (see if repo ok with status)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=folder)
    process.communicate()
    return process.returncode


def input_runner(cmd, run_input, folder):
    # used in git excluded files from .gitignore
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                         stderr=subprocess.STDOUT, cwd=folder)
    out, _ = p.communicate(input=run_input)
    return out


def detect_runner(command):
    # Running detect.py automatic detection of profile
    proc = subprocess.Popen(command, shell=True, bufsize=1, universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    output_buffer = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        # output.write(line)
        output_buffer.append(str(line))

    proc.communicate()
    return proc.returncode, "".join(output_buffer)


def check_output_runner(cmd, stderr=None):
    # Used to run several utilities, like Pacman detect, AIX version, uname, SCM
    d = tempfile.mkdtemp()
    tmp_file = os.path.join(d, "output")
    try:
        # We don't want stderr to print warnings that will mess the pristine outputs
        stderr = stderr or subprocess.PIPE
        cmd = cmd if isinstance(cmd, six.string_types) else subprocess.list2cmdline(cmd)
        command = '{} > "{}"'.format(cmd, tmp_file)
        logger.info("Calling command: {}".format(command))
        process = subprocess.Popen(command, shell=True, stderr=stderr)
        stdout, stderr = process.communicate()
        logger.info("Return code: {}".format(int(process.returncode)))

        if process.returncode:
            # Only in case of error, we print also the stderr to know what happened
            raise CalledProcessErrorWithStderr(process.returncode, cmd, output=stderr)

        output = load(tmp_file)
        try:
            logger.info("Output: in file:{}\nstdout: {}\nstderr:{}".format(output, stdout, stderr))
        except Exception as exc:
            logger.error("Error logging command output: {}".format(exc))
        return output
    finally:
        try:
            rmdir(d)
        except OSError:
            pass
