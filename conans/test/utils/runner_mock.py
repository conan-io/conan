

class RunnerOrderedMock(object):
    """ Class to mock the ConanRunner in tests. It allows to check a sequence of commands
        that has to be provided beforehand (with return values) and would raise if it doesn't
        match actual calls.

        Commands should be provided to the `commands` member variable as a list of tuples where
        the first item of the tuple is the command itself, and the second one is the return value.
    """

    def __init__(self, test_class):
        self.commands = []
        self._test_class = test_class
        self.last_command = None

    def __call__(self, command, output, win_bash=False, subsystem=None):
        self.last_command = command
        if self.is_empty():
            self._test_class.fail("Commands list exhausted, but runner called with '%s'" % command)
        expected, ret = self.commands.pop(0)
        self._test_class.assertEqual(expected, command)
        return ret

    def is_empty(self):
        return not self.commands
