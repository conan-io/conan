from conans.model.ref import ConanFileReference
from conans.client.loader_parse import _parse_file


def conan_python_require(require):
    try:
        conan_python_require._modules
    except AttributeError:
        conan_python_require._modules = {}
    try:
        return conan_python_require._modules[require]
    except KeyError:
        r = ConanFileReference.loads(require)
        path = conan_python_require._proxy.get_recipe(r, False, False)
        module, _ = _parse_file(path)
        conan_python_require._modules[require] = module
    return module
