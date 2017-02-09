import conans


class BuildInfo(object):

    def __init__(self, name=None, number=None, started=None):
        self.modules = []

    def serialize(self):
        return {"modules": [module.serialize() for module in self.modules],
                "buildAgent": {"name": "Conan", "version": conans.__version__}}


class BuildInfoModule(object):

    def __init__(self):
        # Conan package or recipe
        self.id = ""
        self.artifacts = []
        self.dependencies = []

    def serialize(self):
        return {"id": self.id,
                "artifacts": [ar.serialize() for ar in self.artifacts],
                "dependencies": [dep.serialize() for dep in self.dependencies]}


class BuildInfoModuleArtifact(object):

    def __init__(self, the_type, sha1, md5, name):
        # Each file in package
        self._type = the_type
        self._sha1 = sha1
        self._md5 = md5
        self._name = name

    def serialize(self):
        return {"type": self._type,
                "sha1": self._sha1,
                "md5": self._md5,
                "name": self._name}


class BuildInfoModuleDependency(object):

    def __init__(self, the_id, the_type, sha1, md5):
        # Each file in package
        self._the_id = the_id
        self._type = the_type
        self._sha1 = sha1
        self._md5 = md5

    def serialize(self):
        return {"type": self._type,
                "sha1": self._sha1,
                "md5": self._md5,
                "id": self._the_id}
