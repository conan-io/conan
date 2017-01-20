import os
import sys
from subprocess import Popen, PIPE
from conans.util.files import decode_text
from conans.errors import ConanException


class ConanRunner(object):

    def __init__(self, print_commands_to_output=False, generate_run_log=False):
        self._print_commands_to_output = print_commands_to_output
        self._generate_run_log = generate_run_log

    def __call__(self, command, output, log_filepath=None, cwd=None):

        if not self._generate_run_log:
            log_filepath = None

        # Log the command call in output and logger
        call_message = "\n----Running------\n> %s\n-----------------\n" % command
        if self._print_commands_to_output:
            sys.stdout.write(call_message)

        # No output has to be redirected to logs or buffer
        if output is True and not log_filepath:
            return self._simple_os_call(command, cwd)
        elif log_filepath:
            sys.stdout.write("Logging command output to file '%s'\n" % log_filepath)
            with open(log_filepath, "a+") as log_handler:
                if self._print_commands_to_output:
                    log_handler.write(call_message)
                return self._pipe_os_call(command, output, log_handler, cwd)
        else:
            return self._pipe_os_call(command, output, None, cwd)

    def _pipe_os_call(self, command, output_stream, log_handler, cwd):

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
                sys.stdout.write(decoded_line)
                if log_handler:
                    log_handler.write(line)
                if hasattr(output_stream, "write"):
                    output_stream.write(line)

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
