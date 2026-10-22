"""
Splitting an upload in two with --dry-run: the dry run prepares everything (checks the server,
applies the upload_policy, compresses the artifacts) and its package list records what it did, so
feeding that list back to a real upload transfers it without preparing it again.

Preparing is the half that reads recipes, and reading a recipe imports it, which executes its code.
The transfer half does not, so it can be the only step holding the credentials to write.
"""
import json
import os
import platform
import textwrap

import pytest

from conan.api.model import RecipeReference
from conan.internal.util.files import load, save
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer


def _client() -> TestClient:
    """ A client already authenticated, so the several commands each test runs don't have to
    consume the interactive credentials """
    c = TestClient(default_server_user=True, light=True)
    c.run("remote login default admin -p password")
    return c


def _two_servers_client():
    servers = {f"server{i}": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                        users={"user": "password"}) for i in range(2)}
    c = TestClient(servers=servers, inputs=8 * ["user", "password"], light=True)
    for name in servers:
        c.run(f"remote login {name} user -p password")
    return c


def _server_has_sources(server):
    store = server.test_server.server_store.store
    return any("conan_sources.tgz" in files for _, _, files in os.walk(store))


def _break_recipe(client, ref):
    """ Make one recipe in the cache raise as soon as its module is imported. Only the exported
    "e/" copy is touched: the "d/" one is what a prepared list points at, and poisoning that would
    upload a corrupt recipe while the test still passed on its log lines """
    path = client.get_latest_ref_layout(RecipeReference.loads(ref)).conanfile()
    save(path, 'raise Exception("Recipe module executed!")\n' + load(path))


def _break_all_recipes(client):
    broken = 0
    for root, _, files in os.walk(os.path.join(client.cache_folder, "p")):
        if os.path.basename(root) != "e":
            continue
        for f in files:
            if f == "conanfile.py":
                path = os.path.join(root, f)
                save(path, 'raise Exception("Recipe module executed!")\n' + load(path))
                broken += 1
    assert broken, "No exported recipes found in the cache to break"


def test_dry_run_then_upload():
    """ The two halves of an upload, run as separate commands, land the same artifacts as a
    single 'conan upload' does """
    c = _client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("f.txt", "content")})
    c.run("create .")

    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")
    assert "Uploading recipe" not in c.out  # nothing is transferred by the dry run
    c.run("list pkg/1.0:* -r=default")
    assert "ERROR: Recipe not found" in c.out  # nothing reached the server yet

    c.run("upload -l prepared.json -r=default -c")
    assert "pkg/1.0: Uploading recipe" in c.out
    assert "pkg/1.0: Uploading package" in c.out

    # And the artifacts in the server are complete, a different client can consume them
    c2 = TestClient(servers=c.servers, inputs=["admin", "password"], light=True)
    c2.run("install --requires=pkg/1.0")
    assert "pkg/1.0: Downloaded recipe revision" in c2.out
    assert "pkg/1.0: Downloaded package revision" in c2.out
    c2.run("cache path pkg/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    assert load(os.path.join(c2.stdout.strip(), "f.txt")) == "content"


def test_upload_of_a_prepared_list_does_not_load_the_recipes():
    """ The point of the split: the step that holds the credentials for the server does not read
    any recipe, so it cannot execute recipe code """
    c = _client()
    pyreq = textwrap.dedent("""
        from conan import ConanFile
        class MyBase:
            pass
        class PyReq(ConanFile):
            name = "pyreq"
            version = "1.0"
        """)
    pkg = GenConanfile("pkg", "1.0").with_python_requires("pyreq/1.0") \
                                    .with_exports_sources("*.txt")
    c.save({"pyreq/conanfile.py": pyreq, "pkg/conanfile.py": pkg, "pkg/f.txt": "content"})
    c.run("create pyreq")
    c.run("create pkg")

    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")

    _break_all_recipes(c)
    # Sanity check, the recipes in the cache do explode if anything imports them
    c.run("graph info --requires=pkg/1.0", assert_error=True)
    assert "Recipe module executed!" in c.out

    c.run("upload -l prepared.json -r=default -c")
    assert "Recipe module executed!" not in c.out
    assert "pkg/1.0: Uploading recipe" in c.out
    assert "pkg/1.0: Uploading package" in c.out
    assert "pyreq/1.0: Uploading recipe" in c.out

    # And what reached the server is usable, not a poisoned copy
    c2 = TestClient(servers=c.servers, inputs=["admin", "password"], light=True)
    c2.run("install --requires=pkg/1.0")
    assert "pkg/1.0: Downloaded package revision" in c2.out


def test_half_prepared_list_is_rejected():
    """ Only two shapes are supported: a plain "conan list" output, which is prepared and uploaded
    here, or a list keyed by a remote, which has to be fully prepared already. A merge of the two
    is neither, and uploading it would silently leave the unprepared half out """
    c = _client()
    c.save({"conanfile.py": GenConanfile()})
    c.run("create . --name=liba --version=1.0")
    c.run("create . --name=libb --version=1.0")

    c.run("upload liba/1.0 -r=default -c --dry-run --format=json", redirect_stdout="prep.json")
    c.run('list "libb/1.0#*:*#*" --format=json', redirect_stdout="plain.json")
    # Put both in the same set, which is what a half prepared list is
    c.save({"plain.json": c.load("plain.json").replace('"Local Cache"', '"default"', 1)})
    c.run("pkglist merge -l prep.json -l plain.json --format=json", redirect_stdout="mixed.json")

    c.run("upload -l mixed.json -r=default -c", assert_error=True)
    assert "is expected to be fully prepared, but these are not: libb/1.0" in c.out
    assert "A half prepared list is not supported" in c.out
    assert "Traceback" not in c.out
    c.run("list *:* -r=default")
    assert "liba/1.0" not in c.out  # and nothing was uploaded, not even the prepared half


def test_upstream_is_not_re_checked_for_a_prepared_list():
    """ A prepared list is taken at its word: the server is not asked again about it. So whoever
    got there between the dry run and the upload is not noticed, and the artifacts are pushed over
    theirs. This is the race the split buys, and it is a deliberate trade, not an oversight """
    c = _client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")
    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")
    assert "Checking which revisions exist in the remote server" in c.out

    # Someone else uploads that very revision in the meantime
    other = TestClient(servers=c.servers, inputs=2 * ["admin", "password"], light=True)
    other.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    other.run("create .")
    other.run("upload * -r=default -c")
    assert "pkg/1.0: Uploading recipe" in other.out

    # The prepared upload does not ask the server anything, so it does not find out
    c.run("upload -l prepared.json -r=default -c")
    assert "Checking which revisions exist in the remote server" not in c.out
    assert "already in server, skipping upload" not in c.out
    assert "pkg/1.0: Uploading recipe" in c.out  # pushed over what was already there

    # Whereas a single-step upload would have noticed and skipped
    c.run("upload * -r=default -c")
    assert "already in server, skipping upload" in c.out
    assert "Uploading recipe" not in c.out


def test_prepared_list_must_match_the_remote():
    """ A prepared list is keyed by the remote it was prepared against, and what has to be
    uploaded was decided by asking that server what it already had. Uploading it somewhere else
    would upload the wrong things, so it is refused """
    c = _two_servers_client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")
    c.run("upload * -r=server0 -c --dry-run --format=json", redirect_stdout="p0.json")
    assert list(json.loads(c.load("p0.json"))) == ["server0"]

    c.run("upload -l p0.json -r=server1 -c", assert_error=True)
    assert "has entries for the remote 'server0', but 'server1' is the one being uploaded to" \
           in c.out
    assert "prepare the list for 'server1', or upload it to 'server0'" in c.out
    assert "Traceback" not in c.out  # a user mistake, not an internal error
    c.run("list *:* -r=server1")
    assert "pkg/1.0" not in c.out  # and nothing was uploaded anywhere

    # The remote it was prepared for is of course accepted
    c.run("upload -l p0.json -r=server0 -c")
    assert "pkg/1.0: Uploading recipe" in c.out


def test_plain_list_is_not_tied_to_a_remote():
    """ A 'conan list' output is keyed "Local Cache" and says nothing about any remote, so it can
    be uploaded to whichever one is asked for """
    c = _two_servers_client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")
    c.run('list "pkg/1.0#*:*#*" --format=json', redirect_stdout="plain.json")
    assert list(json.loads(c.load("plain.json"))) == ["Local Cache"]

    c.run("upload -l plain.json -r=server1 -c")
    assert "pkg/1.0: Uploading recipe" in c.out
    c.run("upload -l plain.json -r=server0 -c")
    assert "pkg/1.0: Uploading recipe" in c.out


def test_dry_run_applies_the_upload_policy():
    """ upload_policy='skip' is resolved by the dry run, and the transfer honours the list """
    c = _client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")
           .with_class_attribute('upload_policy = "skip"')})
    c.run("create .")
    created_layout = c.created_layout()

    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")
    assert "pkg/1.0: Skipping upload of binaries, because upload_policy='skip'" in c.out
    pkglist = json.loads(c.load("prepared.json"))
    rrev_bundle = pkglist["default"]["pkg/1.0"]["revisions"][created_layout.reference.ref.revision]
    assert rrev_bundle["packages"] == {}

    _break_all_recipes(c)  # the policy is in the list now, no recipe has to be read again
    c.run("upload -l prepared.json -r=default -c")
    assert "Recipe module executed!" not in c.out
    assert "pkg/1.0: Uploading recipe" in c.out
    assert "Uploading package" not in c.out

    c.run("list pkg/1.0:* -r=default")
    assert "No packages found for this revision" in c.out


def test_dry_run_does_not_write_to_the_remote():
    """ The dry run only reads from the remote, so it can be given read-only credentials. Pinned
    here so that adding any write to it fails """
    server = TestServer(read_permissions=[("*/*@*/*", "*")], write_permissions=[],
                        users={"reader": "password"})
    c = TestClient(servers={"default": server}, inputs=4 * ["reader", "password"], light=True)
    c.run("remote login default reader -p password")
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")

    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")
    assert "Permission denied" not in c.out

    # And the transfer is the step that needs write access, so it is the one refused
    c.run("upload -l prepared.json -r=default -c", assert_error=True)
    assert "Permission denied" in c.out


def test_prepared_list_of_what_is_already_in_the_server():
    c = _client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")
    c.run("upload * -r=default -c")

    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")
    assert "already in server, skipping upload" in c.out
    c.run("upload -l prepared.json -r=default -c")
    assert "Uploading recipe" not in c.out
    assert "Uploading package" not in c.out

    # --force belongs to the dry run: it decides what the list says, and the upload obeys it
    # without asking the server again
    c.run("upload * -r=default -c --dry-run --force --format=json", redirect_stdout="forced.json")
    c.run("upload -l forced.json -r=default -c")
    assert "pkg/1.0: Uploading recipe" in c.out


def test_prepared_list_with_only_some_entries_to_upload():
    """ The usual incremental case: the recipe and one binary are already in the server, a second
    binary is new. The dry run marks the first two as not to upload, and preparing computes nothing
    for them, so they carry no urls. They still count as prepared, there is nothing to prepare """
    c = _client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_settings("os")})
    c.run("create . -s os=Linux")
    c.run("upload * -r=default -c")
    c.run("create . -s os=Windows")  # same recipe revision, a new binary
    created_layout = c.created_layout()

    c.run('upload "*:*" -r=default -c --dry-run --format=json', redirect_stdout="prepared.json")

    pkglist = json.loads(c.load("prepared.json"))
    rrev_bundle = pkglist["default"]["pkg/1.0"]["revisions"][created_layout.reference.ref.revision]
    assert rrev_bundle["upload"] is False and "upload-urls" not in rrev_bundle  # nothing to do for the recipe

    prevs = [next(iter(p["revisions"].values())) for p in rrev_bundle["packages"].values()]
    assert sorted(p["upload"] for p in prevs) == [False, True]
    assert [p for p in prevs if p["upload"]][0]["upload-urls"]  # only the new one has urls

    # The list is accepted, and only what was missing is transferred
    c.run("upload -l prepared.json -r=default -c")
    assert "Uploading recipe" not in c.out
    assert c.out.count("Uploading package") == 1


def test_dry_run_only_recipe():
    c = _client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")
    c.run("upload * -r=default -c --dry-run --only-recipe --format=json",
          redirect_stdout="prepared.json")
    c.run("upload -l prepared.json -r=default -c")
    assert "pkg/1.0: Uploading recipe" in c.out
    assert "Uploading package" not in c.out


def test_dry_run_metadata():
    c = _client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")
    ref = RecipeReference.loads("pkg/1.0")
    metadata = os.path.join(c.get_latest_ref_layout(ref).metadata(), "logs", "mylog.txt")
    save(metadata, "log contents")

    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")
    prepared = c.load("prepared.json")
    assert "metadata/logs/mylog.txt" in prepared
    assert "Recipe metadata: 1 files" in c.out
    c.run("upload -l prepared.json -r=default -c -vvv")
    assert "pkg/1.0: Uploading recipe" in c.out
    assert "metadata/logs/mylog.txt" in c.out


@pytest.mark.parametrize("parallel", [1, 2])
def test_dry_run_then_upload_parallel(parallel):
    c = _client()
    c.save_home({"global.conf": f"core.upload:parallel={parallel}"})
    c.save({"conanfile.py": GenConanfile()})
    for index in range(2):
        c.run(f"create . --name=lib{index} --version=1.0")

    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")
    assert (f"Uploading with {parallel} parallel threads" in c.out) is (parallel > 1)
    c.run("upload -l prepared.json -r=default -c")
    assert (f"Uploading with {parallel} parallel threads" in c.out) is (parallel > 1)
    for index in range(2):
        assert f"lib{index}/1.0: Uploading recipe" in c.out
        assert f"lib{index}/1.0: Uploading package" in c.out


def test_prepared_paths_are_absolute():
    """ The prepared list points at the artifacts with absolute paths, so it has to be used
    against the cache that produced it """
    c = _client()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")
    created_layout = c.created_layout()
    c.run("upload * -r=default -c --dry-run --format=json", redirect_stdout="prepared.json")

    pkglist = json.loads(c.load("prepared.json"))
    rrev_bundle = pkglist["default"]["pkg/1.0"]["revisions"][created_layout.reference.ref.revision]
    prev_bundle = rrev_bundle["packages"][created_layout.reference.package_id]["revisions"][created_layout.reference.revision]
    for files in (rrev_bundle["files"], prev_bundle["files"]):
        assert files
        for path in files.values():
            assert os.path.isabs(path)
            assert os.path.isfile(path)  # and they are really there, in this cache


@pytest.mark.parametrize("kind", [
    pytest.param("symlinked_folder",
                 marks=pytest.mark.skipif(platform.system() == "Windows",
                                          reason="symlink need admin privileges")),
    "empty_folder", "regular_file"])
def test_dry_run_retrieves_exports_sources_between_remotes(kind):
    """ Recipes installed from one remote and uploaded to a different one need their exported
    sources fetched first, and that happens in the dry run, which is the half allowed to read the
    recipe.

    Exported sources that are only a symlinked or an empty folder are NOT recorded in the recipe
    manifest although they are uploaded, so any logic deciding this from the manifest loses them
    """
    c = _two_servers_client()
    if kind == "symlinked_folder":
        c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_exports_sources("linked*"),
                "target/data.txt": "content"})
        os.symlink(os.path.join(c.current_folder, "target"),
                   os.path.join(c.current_folder, "linked"))
    elif kind == "empty_folder":
        c.save({"conanfile.py": textwrap.dedent("""
            import os
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                def export_sources(self):
                    os.makedirs(os.path.join(self.export_sources_folder, "placeholder"))
            """)})
    else:
        c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_exports_sources("*.txt"),
                "data.txt": "content"})
    c.run("create .")

    layout = c.get_latest_ref_layout(RecipeReference.loads("pkg/1.0"))
    manifest = load(os.path.join(layout.export(), "conanmanifest.txt"))
    assert ("export_source/" in manifest) is (kind == "regular_file")
    c.run("upload pkg/1.0 -r=server0 -c")
    assert _server_has_sources(c.servers["server0"])

    # Installing brings the recipe, but not its exported sources
    c.run("remove * -c")
    c.run("install --requires=pkg/1.0 -r=server0")
    layout = c.get_latest_ref_layout(RecipeReference.loads("pkg/1.0"))
    assert not os.path.exists(layout.export_sources())

    c.run("upload pkg/1.0 -r=server1 -c --dry-run --format=json", redirect_stdout="prepared.json")
    assert "pkg/1.0: Sources downloaded from 'server0'" in c.out
    c.run("upload -l prepared.json -r=server1 -c")
    assert "pkg/1.0: Uploading recipe" in c.out
    assert _server_has_sources(c.servers["server1"])
