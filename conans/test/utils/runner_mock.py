

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
        if not len(self.commands):
            self._test_class.fail("Commands list exhausted, but runner called with '%s'" % command)
        expected, ret = self.commands.pop(0)
        self._test_class.assertEqual(expected, command)
        return ret


class RunnerMultipleMock(object):
    def __init__(self, expected=None):
        self.calls = 0
        self.expected = expected

    def __call__(self, command, output):  # @UnusedVariable
        self.calls += 1
        return 0 if command in self.expected else 1