import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from io import StringIO

from conans.errors import CalledProcessErrorWithStderr, ConanException
from conans.util.env import environment_update
from conans.util.files import load


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


def conan_run(command, stdout=None, stderr=None, cwd=None, shell=True):
    """
    @param shell:
    @param stderr:
    @param command: Command to execute
    @param stdout: Instead of print to sys.stdout print to that stream. Could be None
    @param cwd: Move to directory to execute
    """
    stdout = stdout or sys.stderr
    stderr = stderr or sys.stderr

    out = subprocess.PIPE if isinstance(stdout, StringIO) else stdout
    err = subprocess.PIPE if isinstance(stderr, StringIO) else stderr

    with pyinstaller_bundle_env_cleaned():
        # Remove credentials before running external application
        with environment_update({'CONAN_LOGIN_ENCRYPTION_KEY': None}):
            try:
                proc = subprocess.Popen(command, shell=shell, stdout=out, stderr=err, cwd=cwd)
            except Exception as e:
                raise ConanException("Error while running cmd\nError: %s" % (str(e)))

            proc_stdout, proc_stderr = proc.communicate()
            # If the output is piped, like user provided a StringIO or testing, the communicate
            # will capture and return something when thing finished
            if proc_stdout:
                stdout.write(proc_stdout.decode("utf-8", errors="ignore"))
            if proc_stderr:
                stderr.write(proc_stderr.decode("utf-8", errors="ignore"))
            return proc.returncode


def version_runner(cmd, shell=False):
    # Used by build subapi like CMake and Meson and MSBuild to get the version
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
        cmd = cmd if isinstance(cmd, str) else subprocess.list2cmdline(cmd)
        command = '{} > "{}"'.format(cmd, tmp_file)
        process = subprocess.Popen(command, shell=True, stderr=stderr)
        stdout, stderr = process.communicate()

        if process.returncode:
            # Only in case of error, we print also the stderr to know what happened
            raise CalledProcessErrorWithStderr(process.returncode, cmd, output=stderr)

        output = load(tmp_file)
        return output
    finally:
        try:
            os.unlink(tmp_file)
        except OSError:
            pass
