from conans.model.ref import ConanFileReference
from conans.client.loader_parse import _parse_file
import sys

_retriever = None


def conan_python_requires(requires):
    for r in requires:
        r = ConanFileReference.loads(r)
        path = _retriever.get_recipe(r)
        module, path = _parse_file(path)
        module.kk = False
        print module
        print module.__dict__.keys()
        print path
        return module

