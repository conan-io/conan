class RunnerExection(Exception):
    def __init__(self, *args, **kwargs):
        self.command = kwargs.pop("command", None)
        self.stdout_log = kwargs.pop("stdout_log", None)
        self.stderr_log = kwargs.pop("stderr_log", None)
        super(RunnerExection, self).__init__(*args, **kwargs)