import codecs
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager

from conan.errors import ConanException
from conan.internal.util.files import load


def _needs_pipe(stream):
    """Streams that are not a file the subprocess can write to on its own, so they need
    a pipe and the output read from it has to be forwarded with write(): the StringIO a
    recipe passes to capture output, subprocess.DEVNULL and the like, or the OutputTee
    that copies the console to the command log when core.log:enabled."""
    if isinstance(stream, int):  # subprocess.DEVNULL and the like
        return False
    try:
        stream.fileno()
    except (AttributeError, ValueError, OSError):  # io.UnsupportedOperation is also this
        return True
    return False


def _forward(pipe, stream):
    """Copies the subprocess output to a Python stream, in chunks and not lines, so a
    progress bar that only writes '\\r' is not withheld until it finishes."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    with pipe:
        for chunk in iter(lambda: pipe.read1(4096), b""):
            stream.write(decoder.decode(chunk))
    pending = decoder.decode(b"", final=True)
    if pending:
        stream.write(pending)


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

    piped_stdout, piped_stderr = _needs_pipe(stdout), _needs_pipe(stderr)
    out = subprocess.PIPE if piped_stdout else stdout
    # A single pipe keeps stdout/stderr in the order the subprocess produced them
    merged = stdout is stderr and piped_stdout
    err = subprocess.STDOUT if merged else (subprocess.PIPE if piped_stderr else stderr)

    with pyinstaller_bundle_env_cleaned():
        try:
            proc = subprocess.Popen(command, shell=shell, stdout=out, stderr=err, cwd=cwd)
        except Exception as e:
            raise ConanException("Error while running cmd\nError: %s" % (str(e)))

        pipes = [(pipe, stream) for pipe, stream in ((proc.stdout, stdout), (proc.stderr, stderr))
                if pipe is not None]
        # Both pipes have to be read at once, or the subprocess blocks when one fills up
        threads = [threading.Thread(target=_forward, args=pipe) for pipe in pipes[1:]]
        for thread in threads:
            thread.start()
        if pipes:
            _forward(*pipes[0])
        for thread in threads:
            thread.join()
        return proc.wait()


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


def check_output_runner(cmd, stderr=None, ignore_error=False):
    # Used to run several utilities, like Pacman detect, AIX version, uname, SCM
    assert isinstance(cmd, str)
    d = tempfile.mkdtemp()
    tmp_file = os.path.join(d, "output")
    try:
        # We don't want stderr to print warnings that will mess the pristine outputs
        stderr = stderr or subprocess.PIPE
        command = '{} > "{}"'.format(cmd, tmp_file)
        process = subprocess.Popen(command, shell=True, stderr=stderr)
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
