import os
import warnings
from contextlib import contextmanager

from conans.errors import ConanV2Exception

CONAN_V2_MODE_ENVVAR = "CONAN_V2_MODE"


def conan_v2_behavior(msg, v1_behavior=None):
    if os.environ.get(CONAN_V2_MODE_ENVVAR, False):
        raise ConanV2Exception(msg)
    else:
        if v1_behavior is None:
            warnings.warn(message=msg, stacklevel=2, category=DeprecationWarning)
        else:
            v1_behavior(msg)


@contextmanager
def conan_v2_property(inst, name, msg):
    if not os.environ.get(CONAN_V2_MODE_ENVVAR, False):
        yield
    else:
        with _conan_v2_property(inst, name, msg):
            yield


@contextmanager
def _conan_v2_property(inst, name, msg):
    original_class = type(inst)

    from conans.model.conan_file import ConanFile
    assert issubclass(original_class, ConanFile), "This function is only intended for ConanFile"

    try:
        def _property_method(_):
            raise ConanV2Exception(msg)

        new_class = type(original_class.__name__, (original_class, ), {})
        inst.__class__ = new_class
        setattr(new_class, name, property(_property_method))
        yield
    finally:
        inst.__class__ = original_class
