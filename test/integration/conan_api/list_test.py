from conan.api.conan_api import ConanAPI
from conan.test.utils.env import environment_update
from conan.internal.model.package_ref import PkgReference
from conan.internal.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_get_recipe_revisions():
    """
    Test the "api.list.recipe_revisions"
    """
    client = TestClient(default_server_user=True)
    for rev in range(1, 4):
        client.save({"conanfile.py": GenConanfile("foo", "1.0").with_build_msg(f"{rev}")})
        client.run("create .")
    client.run("upload * -r=default -c")

    api = ConanAPI(client.cache_folder)
    # Check the revisions locally
    ref = RecipeReference.loads("foo/1.0")
    sot = api.list.recipe_revisions(ref)
    sot = [r.repr_notime() for r in sot]
    assert ["foo/1.0#6707ddcdb444fd46f92d449d11700c5a",
            "foo/1.0#913d984a1b9b8a2821d8c4d4e9cf8d57",
            "foo/1.0#b87cdb893042ec4b371bc6aa82a0108f"] == sot


def test_get_package_revisions():
    """
    Test the "api.list.package_revisions"
    """
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile("foo", "1.0").with_package_file("f.txt",
                                                                              env_var="MYVAR")})
    for rev in range(3):
        with environment_update({"MYVAR": f"{rev}"}):
            client.run("create . ")
    client.run("upload * -r=default -c")

    api = ConanAPI(client.cache_folder)
    # Check the revisions locally
    pref = PkgReference.loads("foo/1.0#77ead28a5fd4216349b5b2181f4d32d4:"
                              "da39a3ee5e6b4b0d3255bfef95601890afd80709")
    sot = api.list.package_revisions(pref)
    sot = [r.repr_notime() for r in sot]
    assert ['foo/1.0#77ead28a5fd4216349b5b2181f4d32d4:'
            'da39a3ee5e6b4b0d3255bfef95601890afd80709#8b34fcf0543672de78ce1fe4f7fb3daa',
            'foo/1.0#77ead28a5fd4216349b5b2181f4d32d4:'
            'da39a3ee5e6b4b0d3255bfef95601890afd80709#5bb077c148d587da50ce9c3212370b5d',
            'foo/1.0#77ead28a5fd4216349b5b2181f4d32d4:'
            'da39a3ee5e6b4b0d3255bfef95601890afd80709#370f42f40d3f353a83a0f529ba2be1ce'] == sot


def test_search_recipes_no_user_channel_only():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name foo --version 1.0 --user user --channel channel")
    client.run("create . --name foo --version 1.0")
    client.run("list foo/1.0@")
    assert "foo/1.0@user/channel" not in client.out
    assert "foo/1.0" in client.out
