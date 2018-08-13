from conans.model.ref import ConanFileReference
from conans.client.loader_parse import _parse_file
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.requires import Requirement


class ConanPythonRequire(object):
    def __init__(self, proxy, range_resolver):
        self._modules = {}
        self._proxy = proxy
        self._range_resolver = range_resolver

    def __call__(self, require):
        try:
            return self._modules[require]
        except KeyError:
            r = ConanFileReference.loads(require)
            requirement = Requirement(r)
            self._range_resolver.resolve(requirement, "python_require", update=False,
                                         remote_name=None)
            r = requirement.conan_reference
            result = self._proxy.get_recipe(r, False, False, remote_name=None,
                                            recorder=ActionRecorder())
            path, _, _, _ = result
            module, _ = _parse_file(path)
            self._modules[require] = module
        return module
