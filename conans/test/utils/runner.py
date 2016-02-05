from conans.client.runner import ConanRunner


class TestRunner(object):
    """Wraps Conan runner and allows to redirect all the ouput to an StrinIO passed
    in the __init__ method"""

    def __init__(self, output):
        self._output = output
        self.runner = ConanRunner()

    def __call__(self, command, output=None, cwd=None):
        return self.runner(command, output=self._output, cwd=cwd)
