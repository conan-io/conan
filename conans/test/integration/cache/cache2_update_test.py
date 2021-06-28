import time
from collections import OrderedDict

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


def test_no_update():
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
    client.run("upload liba/1.0.0 -r server1 --all -c")
    time.sleep(0.1)
    client.run("upload liba/1.0.0 -r server2 --all -c")
    time.sleep(0.1)
    client.run("upload liba/1.0.0 -r server3 --all -c")

    # we already have a revision for this recipe, don't install anything
    client2.run("install liba/1.0.0@")

    # will not find revisions for the recipe -> search all remotes and install the
    # latest revision between all of them, in 2.0 no remotes means search in all of them
    # remote3 has the latest revision so we should pick that one
    # note: we have to consider two cases: the same revision has different dates and also
    # we have different revisions with different dates, if we check server1 and has rev1
    # should we check if theres a newer?
    client.run("remove * -f")
    client.run("install liba/1.0.0@")
    jander = client.out.getvalue()
