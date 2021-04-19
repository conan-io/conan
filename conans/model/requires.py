from collections import OrderedDict

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.env_reader import get_env


class Requirement:
    """ A user definition of a requires in a conanfile
    """
    def __init__(self, ref):
        self.ref = ref

    def __repr__(self):
        return repr(self.ref)

    @property
    def version_range(self):
        """ returns the version range expression, without brackets []
        or None if it is not an expression
        """
        version = self.ref.version
        if version.startswith("[") and version.endswith("]"):
            return version[1:-1]

    def transform_downstream(self, node):
        assert node
        return Requirement(self.ref)

    def __hash__(self):
        return hash(self.ref.name)

    def __eq__(self, other):
        return self.ref.name == other.ref.name

    def __ne__(self, other):
        return not self.__eq__(other)


class Requirements:
    """ User definitions of all requires in a conanfile
    """
    def __init__(self, declared=None):
        self._requires = OrderedDict()
        # Construct from the class definitions
        if declared is not None:
            if isinstance(declared, str):
                declared = [declared, ]
            for item in declared:
                # Todo: Deprecate Conan 1.X definition of tuples, force to use method
                self.__call__(item)

    def values(self):
        return self._requires.values()

    def __call__(self, str_ref):
        assert isinstance(str_ref, str)
        ref = ConanFileReference.loads(str_ref)
        req = Requirement(ref)
        self._requires[req] = req

    def __repr__(self):
        return repr(self._requires.values())

    def override(self, down_reqs, output, own_ref, down_ref):
        """ Compute actual requirement values when downstream values are defined
        param down_reqs: the current requirements as coming from downstream to override
                         current requirements
        param own_ref: ConanFileReference of the current conanfile
        param down_ref: ConanFileReference of the downstream that is overriding values or None
        return: new Requirements() value to be passed upstream
        """

        assert isinstance(down_reqs, Requirements)
        assert isinstance(own_ref, ConanFileReference) if own_ref else True
        assert isinstance(down_ref, ConanFileReference) if down_ref else True

        error_on_override = get_env("CONAN_ERROR_ON_OVERRIDE", False)

        overrides = []
        for req in self._requires:
            down = down_reqs._requires.get(req)
            if down is not None:
                version_range = down.version_range
                current_range = req.version_range
                if version_range is not None:
                    pass
                overrides = [down]

        for override in overrides:
            # Effective override
            self._requires[override] = override




