import os
import sys
from subprocess import Popen, PIPE
from conans.util.files import decode_text
from conans.errors import ConanException


class ConanRunner(object):

    def __call__(self, command, output, log_filepath=None, cwd=None):

        # No output has to be redirected to logs or buffer
        if output is True and not log_filepath:
            return self.simple_os_call(command, cwd)

        if log_filepath:
            with open(log_filepath, "a+") as logfile:
                return self.pipe_os_call(command, output, logfile, cwd)
        else:
            return self.pipe_os_call(command, output, None, cwd)

    def pipe_os_call(self, command, output, log_handler, cwd):

        try:
            proc = Popen(command, shell=True, stdout=PIPE, stderr=PIPE, cwd=cwd)
        except Exception as e:
            raise ConanException("Error while executing '%s'\n\t%s" % (command, str(e)))

        def get_stream_lines(the_stream):
            while True:
                line = the_stream.readline()
                if not line:
                    break
                line = decode_text(line)
                sys.stdout.write(line)
                if log_handler:
                    log_handler.write(line)
                if hasattr(output, "write"):
                    output.write(line)

        get_stream_lines(proc.stdout)
        get_stream_lines(proc.stderr)

        proc.communicate()
        ret = proc.returncode
        return ret

    def simple_os_call(self, command, cwd):
        if not cwd:
            return os.system(command)
        else:
            try:
                old_dir = os.getcwd()
                os.chdir(cwd)
                result = os.system(command)
            except Exception as e:
                raise ConanException("Error while executing '%s'\n\t%s" % (command, str(e)))
            finally:
                os.chdir(old_dir)
            return result
