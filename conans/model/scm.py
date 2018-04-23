

class SCM(object):
    def __init__(self, data):
        self.url = data.get("url")
        self.source = None
        self.commit = data.get("commit")

    @staticmethod
    def get_scm(conanfile):
        data = getattr(conanfile, "scm", None)
        if data is not None:
            return SCM(data)
