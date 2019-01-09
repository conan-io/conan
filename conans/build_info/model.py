from collections import namedtuple

import conans


class BuildInfo(object):

    def __init__(self):
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
                "artifacts": [ar._asdict() for ar in self.artifacts],
                "dependencies": [dep._asdict() for dep in self.dependencies]}


BuildInfoModuleArtifact = namedtuple("BuildInfoModuleArtifact", ['type', 'sha1', 'md5', 'name'])
BuildInfoModuleDependency = namedtuple('BuildInfoModuleDependency', ['id', 'type', 'sha1', 'md5'])
