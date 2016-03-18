import os
from subprocess import Popen, PIPE, STDOUT


class ConanRunner(object):

    def __call__(self, command, output, cwd=None):
        if output is True:
            return os.system(command)
        else:
            proc = Popen(command, shell=True, stdout=PIPE, stderr=STDOUT, cwd=cwd)
            if hasattr(output, "write"):
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    output.write(line.decode())
            out, err = proc.communicate()

            if hasattr(output, "write"):
                if out:
                    output.write(out.decode())
                if err:
                    output.write(err.decode())

            return proc.returncode
