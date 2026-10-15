import pytest
from conan.api.model import Remote
from conan.internal.model.recipe_ref import RecipeReference


@pytest.mark.parametrize("patterns, allowed, rejected", [
    (None, ["pkga/1.0", "zlib/1.0"], []),
    ([], ["pkga/1.0", "zlib/1.0"], []),
    (["pkga/*"], ["pkga/1.0"], ["pkgb/1.0", "zlib/1.0"]),
    (["pkga/*", "zlib/*"], ["pkga/1.0", "zlib/1.0"], ["pkgb/1.0"]),
    # Negations only: everything else is allowed
    (["!pkga/*"], ["pkgb/1.0", "zlib/1.0"], ["pkga/1.0", "pkga/2.0"]),
    (["!pkga/*", "!pkgb/*"], ["zlib/1.0"], ["pkga/1.0", "pkgb/1.0"]),
    (["~pkga/*", "~pkgb/*"], ["zlib/1.0"], ["pkga/1.0", "pkgb/1.0"]),
    (["!pkga/1.*"], ["pkga/2.0", "zlib/1.0"], ["pkga/1.0"]),
    # Negations win over positive matches, whatever the order
    (["pkg*", "!pkgb/*"], ["pkga/1.0"], ["pkgb/1.0", "zlib/1.0"]),
    (["!pkgb/*", "pkg*"], ["pkga/1.0"], ["pkgb/1.0", "zlib/1.0"]),
    (["*", "!pkgb/*"], ["pkga/1.0", "zlib/1.0"], ["pkgb/1.0"]),
    (["pkg*", "!pkgb/*", "!pkga/2.*"], ["pkga/1.0"], ["pkga/2.0", "pkgb/1.0", "zlib/1.0"]),
    # A pattern excluding everything wins over everything
    (["pkga/*", "!*"], [], ["pkga/1.0", "zlib/1.0"]),
])
def test_remote_is_package_allowed(patterns, allowed, rejected):
    remote = Remote("remote", "https://remote", allowed_packages=patterns)
    for ref in allowed:
        assert remote.is_package_allowed(RecipeReference.loads(ref)), f"{ref} should be allowed"
    for ref in rejected:
        assert not remote.is_package_allowed(RecipeReference.loads(ref)), \
            f"{ref} should be rejected"
