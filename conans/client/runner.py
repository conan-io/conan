import io
import os
import sys

from subprocess import PIPE, Popen, STDOUT

import six

from conans.errors import ConanException
from conans.unicode import get_cwd
from conans.util.files import decode_text
from conans.util.runners import pyinstaller_bundle_env_cleaned


class _UnbufferedWrite(object):
    def __init__(self, stream):
        self._stream = stream

    def write(self, *args, **kwargs):
        self._stream.write(*args, **kwargs)
        self._stream.flush()


class ConanRunner(object):

    def __init__(self, print_commands_to_output=False, generate_run_log_file=False,
                 log_run_to_output=True, output=None):
        self._print_commands_to_output = print_commands_to_output
        self._generate_run_log_file = generate_run_log_file
        self._log_run_to_output = log_run_to_output
        self._output = output

    def __call__(self, command, output=True, log_filepath=None, cwd=None, subprocess=False):
        """
        @param command: Command to execute
        @param output: Instead of print to sys.stdout print to that stream. Could be None
        @param log_filepath: If specified, also log to a file
        @param cwd: Move to directory to execute
        """
        if output and isinstance(output, io.StringIO) and six.PY2:
            # in py2 writing to a StringIO requires unicode, otherwise it fails
            print("*** WARN: Invalid output parameter of type io.StringIO(), "
                  "use six.StringIO() instead ***")

        stream_output = output if output and hasattr(output, "write") else self._output or sys.stdout
        if hasattr(output, "flush"):
            # We do not want output from different streams to get mixed (sys.stdout, os.system)
            stream_output = _UnbufferedWrite(stream_output)

        if not self._generate_run_log_file:
            log_filepath = None

        # Log the command call in output and logger
        call_message = "\n----Running------\n> %s\n-----------------\n" % command
        if self._print_commands_to_output and stream_output and self._log_run_to_output:
            stream_output.write(call_message)

        with pyinstaller_bundle_env_cleaned():
            # No output has to be redirected to logs or buffer or omitted
            if (output is True and not self._output and not log_filepath and self._log_run_to_output
                    and not subprocess):
                return self._simple_os_call(command, cwd)
            elif log_filepath:
                if stream_output:
                    stream_output.write("Logging command output to file '%s'\n" % log_filepath)
                with open(log_filepath, "a+") as log_handler:
                    if self._print_commands_to_output:
                        log_handler.write(call_message)
                    return self._pipe_os_call(command, stream_output, log_handler, cwd)
            else:
                return self._pipe_os_call(command, stream_output, None, cwd)

    def _pipe_os_call(self, command, stream_output, log_handler, cwd):

        try:
            # piping both stdout, stderr and then later only reading one will hang the process
            # if the other fills the pip. So piping stdout, and redirecting stderr to stdout,
            # so both are merged and use just a single get_stream_lines() call
            proc = Popen(command, shell=True, stdout=PIPE, stderr=STDOUT, cwd=cwd)
        except Exception as e:
            raise ConanException("Error while executing '%s'\n\t%s" % (command, str(e)))

        def get_stream_lines(the_stream):
            while True:
                line = the_stream.readline()
                if not line:
                    break
                decoded_line = decode_text(line)
                if stream_output and self._log_run_to_output:
                    try:
                        stream_output.write(decoded_line)
                    except UnicodeEncodeError:  # be aggressive on text encoding
                        decoded_line = decoded_line.encode("latin-1", "ignore").decode("latin-1",
                                                                                       "ignore")
                        stream_output.write(decoded_line)

                if log_handler:
                    # Write decoded in PY2 causes some ASCII encoding problems
                    # tried to open the log_handler binary but same result.
                    log_handler.write(line if six.PY2 else decoded_line)

        get_stream_lines(proc.stdout)
        # get_stream_lines(proc.stderr)

        proc.communicate()
        ret = proc.returncode
        return ret

    def _simple_os_call(self, command, cwd):
        if not cwd:
            return os.system(command)
        else:
            try:
                old_dir = get_cwd()
                os.chdir(cwd)
                result = os.system(command)
            except Exception as e:
                raise ConanException("Error while executing"
                                     " '%s'\n\t%s" % (command, str(e)))
            finally:
                os.chdir(old_dir)
            return result
