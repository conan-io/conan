import os
import sys
from subprocess import Popen, PIPE
from conans.util.files import decode_text
from conans.errors import ConanException
import six


class ConanRunner(object):

    def __init__(self, print_commands_to_output=False, generate_run_log_file=False, log_run_to_output=True):
        self._print_commands_to_output = print_commands_to_output
        self._generate_run_log_file = generate_run_log_file
        self._log_run_to_output = log_run_to_output

    def __call__(self, command, output, log_filepath=None, cwd=None):
        """
        @param command: Command to execute
        @param output: Instead of print to sys.stdout print to that stream. Could be None
        @param log_filepath: If specified, also log to a file
        @param cwd: Move to directory to execute
        """
        stream_output = output if output and hasattr(output, "write") else sys.stdout

        if not self._generate_run_log_file:
            log_filepath = None

        # Log the command call in output and logger
        call_message = "\n----Running------\n> %s\n-----------------\n" % command
        if self._print_commands_to_output and stream_output and self._log_run_to_output:
            stream_output.write(call_message)

        # No output has to be redirected to logs or buffer or omitted
        if output is True and not log_filepath and self._log_run_to_output:
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
            proc = Popen(command, shell=True, stdout=PIPE, stderr=PIPE, cwd=cwd)
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
                    except UnicodeEncodeError:  # be agressive on text encoding
                        decoded_line = decoded_line.encode("latin-1", "ignore").decode("latin-1",
                                                                                       "ignore")
                        stream_output.write(decoded_line)

                if log_handler:
                    # Write decoded in PY2 causes some ASCII encoding problems
                    # tried to open the log_handler binary but same result.
                    log_handler.write(line if six.PY2 else decoded_line)

        get_stream_lines(proc.stdout)
        get_stream_lines(proc.stderr)

        proc.communicate()
        ret = proc.returncode
        return ret

    def _simple_os_call(self, command, cwd):
        if not cwd:
            return os.system(command)
        else:
            try:
                old_dir = os.getcwd()
                os.chdir(cwd)
                result = os.system(command)
            except Exception as e:
                raise ConanException("Error while executing"
                                     " '%s'\n\t%s" % (command, str(e)))
            finally:
                os.chdir(old_dir)
            return result
