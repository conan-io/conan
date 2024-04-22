import os
import platform
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from io import StringIO

from conans.errors import ConanException
from conans.util.files import load


if getattr(sys, 'frozen', False) and 'LD_LIBRARY_PATH' in os.environ:

    # http://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
    pyinstaller_bundle_dir = os.environ['LD_LIBRARY_PATH'].replace(
        os.environ.get('LD_LIBRARY_PATH_ORIG', ''), ''
    ).strip(';:')

    @contextmanager
    def pyinstaller_bundle_env_cleaned():
        """Removes the pyinstaller bundle directory from LD_LIBRARY_PATH
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


# Windows (and possibly other platforms) should have a clean environment,
# unpolluted by anything in the user's environment.
# Anything except the bare minimum should be added to the environment through
# conan's environment mechanisms.
# This whitelist could potentially be slimmed down further.
def _env_for_Popen():
    newenv = None
    if platform.system() == 'Windows':
        whitelist_env_keys = [
                'ALLUSERSPROFILE',
                'APPDATA',
                'CommonProgramFiles',
                'CommonProgramFiles(x86)',
                'CommonProgramW6432',
                'COMPUTERNAME',
                'ComSpec',
                'DriverData',
                'HOMEDRIVE',
                'HOMEPATH',
                'LOCALAPPDATA',
                'LOGONSERVER',
                'NUMBER_OF_PROCESSORS',
                'OS',
                'PATHEXT',
                'PROCESSOR_ARCHITECTURE',
                'PROCESSOR_IDENTIFIER',
                'PROCESSOR_LEVEL',
                'PROCESSOR_REVISION',
                'ProgramData',
                'ProgramFiles',
                'ProgramFiles(x86)',
                'ProgramW6432',
                'PUBLIC',
                'SESSIONNAME',
                'SystemDrive',
                'SystemRoot',
                'TEMP',
                'TMP',
                'USERDOMAIN',
                'USERDOMAIN_ROAMINGPROFILE',
                'USERNAME',
                'USERPROFILE',
                'windir'
                ]
        newenv = { key: os.environ[key] for key in whitelist_env_keys }
        newenv['Path'] = 'C:\\WINDOWS\\system32;C:\\WINDOWS'
    return newenv


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
        try:
            proc = subprocess.Popen(command, shell=shell, stdout=out, stderr=err, cwd=cwd, env=_env_for_Popen())
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


def detect_runner(command):
    # Running detect.py automatic detection of profile
    proc = subprocess.Popen(command, shell=True, bufsize=1, universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=_env_for_Popen())

    output_buffer = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        # output.write(line)
        output_buffer.append(str(line))

    proc.communicate()
    return proc.returncode, "".join(output_buffer)


def check_output_runner(cmd, stderr=None, ignore_error=False):
    # Used to run several utilities, like Pacman detect, AIX version, uname, SCM
    assert isinstance(cmd, str)
    d = tempfile.mkdtemp()
    tmp_file = os.path.join(d, "output")
    try:
        # We don't want stderr to print warnings that will mess the pristine outputs
        stderr = stderr or subprocess.PIPE
        command = '{} > "{}"'.format(cmd, tmp_file)
        process = subprocess.Popen(command, shell=True, stderr=stderr, env=_env_for_Popen())
        stdout, stderr = process.communicate()

        if process.returncode and not ignore_error:
            # Only in case of error, we print also the stderr to know what happened
            msg = f"Command '{cmd}' failed with errorcode '{process.returncode}'\n{stderr}"
            raise ConanException(msg)

        output = load(tmp_file)
        return output
    finally:
        try:
            os.unlink(tmp_file)
        except OSError:
            pass
