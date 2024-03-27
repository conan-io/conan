class SSHRunner:

    def __init__(self, conan_api, command, profile, args, raw_args):
        self.conan_api = conan_api
        self.command = command
        self.profile = profile
        self.args = args
        self.raw_args = raw_args

    def run(self, use_cache=True):
        pass
