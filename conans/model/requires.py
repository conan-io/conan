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


class Requirements:
    """ User definitions of all requires in a conanfile
    """
    def __init__(self, declared=None):
        self._requires = []
        # Construct from the class definitions
        if declared is not None:
            if isinstance(declared, str):
                declared = [declared, ]
            for item in declared:
                # Todo: Deprecate Conan 1.X definition of tuples, force to use method
                self.__call__(item)

    def __iter__(self):
        return iter(self._requires)

    def __next__(self):
        return next(self._requires)

    def __call__(self, str_ref):
        assert isinstance(str_ref, str)
        ref = ConanFileReference.loads(str_ref)
        self._requires.append(Requirement(ref))

    def __repr__(self):
        return repr(self._requires)

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

        new_reqs = Requirements()
        # FIXME: IMplement this
        return new_reqs
        for req in self._requires:
            if name in down_reqs and not req.locked_id:
                other_req = down_reqs[name]
                # update dependency
                other_ref = other_req.ref
                if other_ref and other_ref != req.ref:
                    down_reference_str = str(down_ref) if down_ref else ""
                    msg = "%s: requirement %s overridden by %s to %s " \
                          % (own_ref, req.ref, down_reference_str or "your conanfile", other_ref)

                    if error_on_override and not other_req.override:
                        raise ConanException(msg)

                    output.warn(msg)
                    req.ref = other_ref
                    # FIXME: We should compute the intersection of version_ranges
                    if req.version_range and not other_req.version_range:
                        req.range_ref = other_req.range_ref  # Override

            new_reqs[name] = req
        return new_reqs



