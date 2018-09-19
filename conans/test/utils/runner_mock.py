

class RunnerOrderedMock(object):

    def __init__(self, test_class):
        self.commands = []
        self._test_class = test_class

    def __call__(self, command, output, win_bash=False, subsystem=None):
        if self.is_empty():
            self._test_class.fail("Commands list exhausted, but runner called with '%s'" % command)
        expected, ret = self.commands.pop(0)
        self._test_class.assertEqual(expected, command)
        return ret

    def is_empty(self):
        return not self.commands
