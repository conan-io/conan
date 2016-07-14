import os
from subprocess import Popen, PIPE, STDOUT
from conans.util.files import decode_text
from conans.errors import ConanException


class ConanRunner(object):

    def __call__(self, command, output, cwd=None):
        """ There are two options, with or without you (sorry, U2 pun :)
        With or without output. Probably the Popen approach would be fine for both cases
        but I found it more error prone, slower, problems with very large outputs (typical
        when building C/C++ projects...) so I prefer to keep the os.system one for
        most cases, in which the user does not want to capture the output, and the Popen
        for cases they want
        """
        if output is True:
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
        else:
            proc = Popen(command, shell=True, stdout=PIPE, stderr=STDOUT, cwd=cwd)
            if hasattr(output, "write"):
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    output.write(decode_text(line))
            out, err = proc.communicate()

            if hasattr(output, "write"):
                if out:
                    output.write(decode_text(out))
                if err:
                    output.write(decode_text(err))

            return proc.returncode
