

class RunnerMock(object):
    def __init__(self, return_ok=True):
        self.command_called = None
        self.return_ok = return_ok

    def __call__(self, command, output, win_bash=False, subsystem=None):  # @UnusedVariable
        self.command_called = command
        self.win_bash = win_bash
        self.subsystem = subsystem
        return 0 if self.return_ok else 1


class RunnerOrderedMock(object):
    commands = []  # Command + return value

    def __init__(self, test_class):
        self._test_class = test_class

    def __call__(self, command, output, win_bash=False, subsystem=None):
        if self.is_empty():
            self._test_class.fail("Commands list exhausted, but runner called with '%s'" % command)
        expected, ret = self.commands.pop(0)
        self._test_class.assertEqual(expected, command)
        return ret

    def is_empty(self):
        return not self.commands
