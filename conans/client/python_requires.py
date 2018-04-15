from conans.model.ref import ConanFileReference
from conans.client.loader_parse import _parse_file

_retriever = None  # proxy to retrieve recipes
_modules = {}  # Private dict for caching already parsed modules


def conan_python_require(require):
    try:
        return _modules[require]
    except KeyError:
        r = ConanFileReference.loads(require)
        path = _retriever.get_recipe(r)
        module, _ = _parse_file(path)
        _modules[require] = module
        return module
