import pytest

from conan import ConanFile
from conan.errors import ConanException
from conan.internal.errors import conanfile_remove_attr


class _Base(ConanFile):
    pass


class _Pkg(_Base):
    pass


def test_forbidden_attributes():
    c = _Pkg(None)
    with conanfile_remove_attr(c, ["settings", "cpp_info"], "package_id"):
        assert isinstance(c, _Pkg)
        with pytest.raises(ConanException,
                           match=r"'self.settings' access in 'package_id\(\)' method is forbidden"):
            c.settings  # noqa
        with pytest.raises(ConanException, match="'self.cpp_info' access in 'package_id"):
            c.cpp_info  # noqa
    assert type(c) is _Pkg
    c.settings  # noqa

    with pytest.raises(ZeroDivisionError):
        with conanfile_remove_attr(c, ["settings"], "validate"):
            1 / 0
    assert type(c) is _Pkg


def test_subclass_created_once():
    """ The subclass is created once per recipe class, method and attributes, not in every call,
    so it doesn't leave garbage with reference cycles (never freed with the GC disabled) """
    a, b = _Pkg(None), _Pkg(None)
    with conanfile_remove_attr(a, ["settings"], "package_id"):
        cls = type(a)
    with conanfile_remove_attr(b, ["settings"], "package_id"):
        assert type(b) is cls
    with conanfile_remove_attr(b, ["settings"], "validate"):
        assert type(b) is not cls
        with pytest.raises(ConanException, match=r"in 'validate\(\)' method is forbidden"):
            b.settings  # noqa
    with conanfile_remove_attr(b, ["settings", "options"], "package_id"):
        assert type(b) is not cls
        with pytest.raises(ConanException, match="'self.options' access"):
            b.options  # noqa

    # Kept in the recipe class itself, not inherited by the ones derived from it
    base = _Base(None)
    with conanfile_remove_attr(base, ["settings"], "package_id"):
        assert type(base).__bases__ == (_Base, )
