from conans.model.ref import ConanFileReference
from conans.client.loader_parse import _parse_file


class ConanPythonRequire(object):
    def __init__(self, proxy):
        self._proxy = proxy  # To fetch recipes
        self._modules = {}  # cached modules

    def __call__(self, require):
        try:
            return self._modules[require]
        except KeyError:
            r = ConanFileReference.loads(require)
            path = self._proxy.get_recipe(r, False, False)
            module, _ = _parse_file(path)
            self._modules[require] = module
            return module
