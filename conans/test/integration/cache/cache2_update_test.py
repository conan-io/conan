import time
from collections import OrderedDict

from mock import patch

from conans.model.ref import ConanFileReference
from conans.server.revision_list import RevisionList
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


def test_update_flows():
    # - when a revision is installed from a remote it takes the date from the remote, not
    # creating a new one
    # - if we want to install the revision and create it with a new date use --update-date
    # (name to be revisited)
    servers = OrderedDict()
    for index in range(3):
        servers[f"server{index + 1}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"lasote": "mypass"})

    client = TestClient(servers=servers)
    client2 = TestClient(servers=servers)

    for index in range(3):
        client.run(f"user lasote -p mypass -r server{index + 1}")
        client2.run(f"user lasote -p mypass -r server{index + 1}")

    # create a new rrev, client2 will have an older revision than all the servers
    client2.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new revision 0")})
    client2.run("create .")

    # upload the same revision, will have different timestamps on each server
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0")})
    client.run("remote list")
    client.run("create .")

    # all these revisions uploaded to the servers will be older than the ones we create in local
    the_time = time.time() - 1000

    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    # upload other revision
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new revision 1")})
    client.run("create .")
    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    # TESTING WITHOUT SPECIFIC REVISIONS AND WITH NO REMOTES: conan install liba/1.0.0
    # - In conan 2.X no remote means search in all remotes

    # client2 already has a revision for this recipe, don't install anything
    client2.run("install liba/1.0.0@")
    assert "liba/1.0.0 from local cache - Cache" in client2.out
    assert "liba/1.0.0: Already installed!" in client2.out

    client.run("remove * -f")

    # will not find revisions for the recipe -> search all remotes and install the
    # latest revision between all of them, in 2.0 no remotes means search in all of them
    # remote3 has the latest revision so we should pick that one
    # --> result: install rev from remote3
    client.run("install liba/1.0.0@")
    assert "liba/1.0.0 from 'server3' - Downloaded" in client.out
    assert "liba/1.0.0: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" \
           " from remote 'server3'" in client.out

    # It will first check all the remotes and
    # will find the latest revision: rev from server3
    # --> result: we already have the revision installed so do nothing
    client.run("install liba/1.0.0@ --update")
    assert "liba/1.0.0 from 'server3' - Cache" in client.out
    assert "liba/1.0.0: Already installed!" in client.out

    client.run("remove * -f")

    # we create a newer revision in client
    # we already have a revision for liba/1.0.0 so don't install anything
    # --> result: don't install anything
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new revision 2")})
    client.run("create .")
    client.run("install liba/1.0.0@")
    assert "liba/1.0.0: Already installed!" in client.out

    # we already have a newer revision in the client
    # we will check all the remotes, find the latest revision
    # this revision will be oldest than the one in the cache
    # --> result: don't install anything
    client.run("install liba/1.0.0@ --update")
    assert "liba/1.0.0 from local cache - Newer" in client.out
    assert "liba/1.0.0: Already installed!" in client.out

    # create newer revisions in servers so that the ones from the clients are older
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new rev in servers")})
    client.run("create .")
    the_time = time.time()
    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    # now check for newer references with --update for client2 that has an older revision
    # when we use --update: first check all remotes (no -r argument) get latest revision
    # check if it is in cache, if it is --> stop, if it is not --> check date and install
    # --> result: install rev from server3
    client2.run("install liba/1.0.0@ --update")
    assert "liba/1.0.0 from 'server3' - Updated" in client2.out
    assert "liba/1.0.0: Downloaded recipe revision 358f80db50845bf1ffb32f4a7ab562f7" in client2.out
    assert "liba/1.0.0: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" \
           " from remote 'server3'" in client2.out

    # TESTING WITH SPECIFIC REVISIONS AND WITH NO REMOTES: conan install liba/1.0.0#rrev
    # - In conan 2.X no remote means search in all remotes

    # check one revision we already have will not be installed
    # we search for that revision in the cache, we found it
    # --> result: don't install that
    latest_rrev = client.cache.get_latest_rrev(ConanFileReference.loads("liba/1.0.0"))
    client.run(f"install {latest_rrev}@#{latest_rrev.revision}")
    assert "liba/1.0.0 from 'server1' - Cache" in client.out
    assert "liba/1.0.0: Already installed!" in client.out

    client.run("remove * -f")

    client.run("remove '*' -f -r server1")
    client.run("remove '*' -f -r server2")
    client.run("remove '*' -f -r server3")

    # create older revisions in servers
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("older rev in servers")})
    client.run("create .")
    server_rrev = client.cache.get_latest_rrev(ConanFileReference.loads("liba/1.0.0"))
    the_time = time.time() - 100
    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    client.run("remove * -f")

    # have a newer different revision in the cache, but ask for an specific revision that is in
    # the servers, will try to find that revision and install it from the first server found
    # will not check all the remotes for the latest
    # --> result: install new revision asked, but the latest revision remains the other one, because
    # the one installed took the date from the server and it's older
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("newer rev cache")})
    client.run("create .")
    client.run(f"install {server_rrev}@#{server_rrev.revision}")
    assert "liba/1.0.0: Not found in local cache, looking in remotes..." in client.out
    assert "liba/1.0.0: Checking all remotes: (server1, server2, server3)" in client.out
    assert "liba/1.0.0: Checking remote: server1" in client.out
    assert "liba/1.0.0: Checking remote: server2" not in client.out
    assert "liba/1.0.0: Checking remote: server3" not in client.out
    assert "liba/1.0.0: Trying with 'server1'..." in client.out
    latest_cache_revision = client.cache.get_latest_rrev(server_rrev.copy_clear_rev())
    assert latest_cache_revision != server_rrev

    # now we have the same revision with different dates in the servers and in the cache
    # in this case, if we specify --update should we check all remotes and try to install the
    # latest one or just take the first (same behaviour that the one without --update)
    # TODO: cache2.0 --update flows check the desired behaviour here

    client.run("remove * -f")
    client.run("remove '*' -f -r server1")
    client.run("remove '*' -f -r server2")
    client.run("remove '*' -f -r server3")

    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new case")})
    client.run("create .")
    server_rrev = client.cache.get_latest_rrev(ConanFileReference.loads("liba/1.0.0"))
    the_time = time.time() + 10
    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    client.run(f"install {server_rrev}@#{server_rrev.revision} --update")


def test_update_flows_version_ranges():
    pass
