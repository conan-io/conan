import os
import warnings
from contextlib import contextmanager

from conans.errors import ConanV2Exception

CONAN_V2_MODE_ENVVAR = "CONAN_V2_MODE"


def conan_v2_behavior(msg, v1_behavior=None):
    if os.environ.get(CONAN_V2_MODE_ENVVAR, False):
        msg = "Conan v2 incompatible: {}".format(msg)
        # TODO: Add a link to a public webpage with Conan roadmap to v2
        raise ConanV2Exception(msg)
    else:
        if v1_behavior is None:
            warnings.warn(message=msg, stacklevel=2, category=DeprecationWarning)
        else:
            v1_behavior(msg)


@contextmanager
def conan_v2_property(inst, name, msg, v1_behavior=None):
    original_class = type(inst)

    from conans.model.conan_file import ConanFile
    assert issubclass(original_class, ConanFile), "This function is only intended for ConanFile"

    try:
        original_value = getattr(inst, name, 'None')

        def _property_method(_):
            conan_v2_behavior(msg, v1_behavior)
            return original_value

        new_class = type(original_class.__name__, (original_class, ), {})
        inst.__class__ = new_class
        setattr(new_class, name, property(_property_method))
        yield
    finally:
        inst.__class__ = original_class
