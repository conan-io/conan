import time
from collections import OrderedDict

from mock import patch

from conans.server.revision_list import RevisionList
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


def test_update_flows():

    # - when a revision is installed from a remote it takes the date from the remote, not
    # creating a new one
    # - if we want to install the revision and create it with a new date use --update-date
    # (name to be revisited)

    server1 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
    server2 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
    server3 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
    servers = OrderedDict()
    servers["server1"] = server1
    servers["server2"] = server2
    servers["server3"] = server3
    client = TestClient(servers=servers)
    client.run("user lasote -p mypass -r server1")
    client.run("user lasote -p mypass -r server2")
    client.run("user lasote -p mypass -r server3")

    client2 = TestClient(servers=servers)
    client2.run("user lasote -p mypass -r server1")
    client2.run("user lasote -p mypass -r server2")
    client2.run("user lasote -p mypass -r server3")

    # create a new rrev, client2 has an older revision than all the servers
    client2.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_provides("somelib/1.0.0")})
    client2.run("create .")

    # upload the same revision, will have different timestamps on each server
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0")})
    client.run("remote list")
    client.run("create .")
    # same revision with different datest
    # TODO: different revision with different dates
    the_time = time.time()

    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_provides("new_revision/1.0.0")})
    client.run("create .")

    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    # client2 already has a revision for this recipe, don't install anything
    client2.run("install liba/1.0.0@")
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

    # now check for newer references with --update for client2 that has an older revision
    # when we use --update: first check all remotes (no -r argument) get latest revision
    # check if it is in cache, if it is --> stop, if it is not --> check date and install
    # --> result: install rev from server3
    client2.run("install liba/1.0.0@ --update")
    assert "liba/1.0.0: Downloaded recipe revision 70d7d7aab6c02d9c44d7418a7a33d120" in client2.out
    assert "liba/1.0.0: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" \
           " from remote 'server3'" in client2.out

    # note: we have to consider two cases: the same revision has different dates and also
    # we have different revisions with different dates, if we check server1 and has rev1
    # should we check if theres a newer?


def test_update_flows_version_ranges():
    pass
