from collections import OrderedDict
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
import six


class Requirement(object):
    """ A reference to a conans plus some attributes of how to
    depend on that conans
    """
    def __init__(self, conan_reference, private=False, override=False):
        """
        param override: True means that this is not an actual requirement, but something to
                        be passed upstream and override possible existing values
        param private: True means that this requirement will be somewhat embedded (like
                       a static lib linked into a shared lib), so it is not required to link
        """
        self.conan_reference = conan_reference
        self.private = private
        self.override = override

    def __repr__(self):
        return ("%s" % str(self.conan_reference) +
               (" P" if self.private else ""))

    def __eq__(self, other):
        return (self.override == other.override and
                self.conan_reference == other.conan_reference and
                self.private == other.private)

    def __ne__(self, other):
        return not self.__eq__(other)
    


class Requirements(OrderedDict):
    """ {name: Requirement} in order, e.g. {"Hello": Requirement for Hello}
    """
    # auxiliary class variable so output messages when overriding requirements
    # FIXME: A more elegant solution
    output = None

    def __init__(self, *args):
        super(Requirements, self).__init__()
        for v in args:
            if isinstance(v, tuple):
                override = private = False
                ref = v[0]
                for elem in v[1:]:
                    if elem == "override":
                        override = True
                    elif elem == "private":
                        private = True
                    else:
                        raise ConanException("Unknown requirement config %s" % elem)
                self.add(ref, private=private, override=override)
            else:
                self.add(v)

    def copy(self):
        """ We need a custom copy as the normal one requires __init__ to be
        properly defined
        """
        result = Requirements()
        for name, req in self.items():
            result[name] = req
        return result

    def iteritems(self): # FIXME: Just a trick to not change the default testing conanfile for python 3
        return self.items()

    def add(self, reference, private=False, override=False):
        """ to define requirements by the user in text, prior to any propagation
        """
        assert isinstance(reference, six.string_types)
        try:
            conan_reference = ConanFileReference.loads(reference)
            name = conan_reference.name
        except ConanException:
            conan_reference = None
            name = reference

        new_requirement = Requirement(conan_reference, private, override)
        old_requirement = self.get(name)
        if old_requirement and old_requirement != new_requirement:
            self.output.warn("Duplicated requirement %s != %s"
                             % (old_requirement, new_requirement))
        else:
            self[name] = new_requirement

    def update(self, down_reqs, output, own_ref, down_ref):
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

        new_reqs = down_reqs.copy()
        if own_ref:
            new_reqs.pop(own_ref.name, None)
        for name, req in self.items():
            if name in down_reqs:
                other_req = down_reqs[name]
                # update dependency
                other_ref = other_req.conan_reference
                if other_ref and other_ref != req.conan_reference:
                    output.info("%s requirement %s overriden by %s to %s "
                                % (own_ref, req.conan_reference, down_ref or "your conanfile",
                                   other_ref))
                    req.conan_reference = other_ref

            new_reqs[name] = req
        return new_reqs

    def __call__(self, conan_reference, private=False, override=False):
        self.add(conan_reference, private, override)

    def __repr__(self):
        result = []
        for req in self.values():
            result.append(str(req))
        return '\n'.join(result)
