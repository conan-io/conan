from conans.client.runner import ConanRunner


class TestRunner(object):
    """Wraps Conan runner and allows to redirect all the ouput to an StrinIO passed
    in the __init__ method"""

    def __init__(self, output, runner=None):
        self._output = output
        self.runner = runner or ConanRunner(print_commands_to_output=True,
                                            generate_run_log_file=True,
                                            log_run_to_output=True)

    def __call__(self, command, output=None, log_filepath=None, cwd=None):
        return self.runner(command, output=self._output, log_filepath=log_filepath, cwd=cwd)
