from contextlib import contextmanager

from conans.errors import ConanException


@contextmanager
def conan_v2_property(inst, name, msg):
    original_class = type(inst)

    try:
        def _property_method(_):
            raise ConanException(msg)

        new_class = type(original_class.__name__, (original_class, ), {})
        inst.__class__ = new_class
        setattr(new_class, name, property(_property_method))
        yield
    finally:
        inst.__class__ = original_class
