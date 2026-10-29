import os

import pytest

from conan.api.model import RecipeReference
from conan.internal.cache.cache import PkgCache
from conan.internal.model.conf import ConfDefinition
from conan.test.utils.test_files import temp_folder

REFS = ["pkg/1.0", "pkg/1.2.0", "pkg/2.0@user/channel", "pkg-extra/1.0", "pkg0/1.0", "pkg_other/1.0",
        "pkgfoo/1.0", "zlib/1.3.1", "zlib/1.2.13@user/testing", "a/1.0", "ab/1.0", "Mixed/1.0"]


@pytest.fixture(scope="module")
def cache():
    folder = temp_folder()
    cache = PkgCache(folder, ConfDefinition())
    for i, text in enumerate(REFS):
        for rev in ("rev1", "rev2"):  # revisions must not duplicate the references
            ref = RecipeReference.loads(f"{text}#{rev}%{i + 1}")
            cache._db.create_recipe(os.path.join(folder, f"folder{i}_{rev}"), ref)
    return cache


@pytest.mark.parametrize("pattern, name", [("pkg/*", "pkg"), ("pkg/*@user/channel", "pkg"),
                                           ("zlib/*", "zlib"), ("zlib/*@user/testing", "zlib"),
                                           ("a/*", "a"), ("ab/*", "ab"), ("pkg0/*", "pkg0"),
                                           ("pkg_other/*", "pkg_other"), ("nomatch/*", "nomatch"),
                                           ("mixed/*", "mixed"), ("Mixed/*", "Mixed")])
def test_search_recipes_name_is_equivalent_to_full_scan(cache, pattern, name):
    """ The name is only an optimization of the DB query, results must be the same as filtering
    all the references with the pattern"""
    expected = cache.search_recipes(pattern)
    result = cache.search_recipes(pattern, name=name)
    assert sorted(map(str, result)) == sorted(map(str, expected))
    assert len(set(map(str, result))) == len(result)


def test_search_recipes_name_results(cache):
    assert sorted(map(str, cache.search_recipes("pkg/*", name="pkg"))) == \
           ["pkg/1.0", "pkg/1.2.0", "pkg/2.0@user/channel"]
    assert [str(r) for r in cache.search_recipes("pkg/*@user/channel", name="pkg")] == \
           ["pkg/2.0@user/channel"]
    assert [str(r) for r in cache.search_recipes("a/*", name="a")] == ["a/1.0"]
    assert [str(r) for r in cache.search_recipes("nomatch/*", name="nomatch")] == []
    assert len(cache.search_recipes()) == len(REFS)
    ref = RecipeReference.loads("zlib/*")
    assert sorted(map(str, cache.search_recipes(ref, name="zlib"))) == \
           ["zlib/1.2.13@user/testing", "zlib/1.3.1"]
