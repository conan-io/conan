from subprocess import PIPE, Popen, STDOUT


class TestRunner(object):
    def __init__(self, output):
        self._output = output

    def __call__(self, command, cwd=None):
        proc = Popen(command, shell=True, bufsize=1, stdout=PIPE, stderr=STDOUT, cwd=cwd)

        while True:
            line = proc.stdout.readline()
            if not line:
                break
            self._output.write(line)

        out, err = proc.communicate()

        if out:
            self._output.write(out)
        if err:
            self._output.write(err)

        return proc.returncode
