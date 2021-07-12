import time
from collections import OrderedDict

from mock import patch

from conans.model.ref import ConanFileReference
from conans.server.revision_list import RevisionList
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


def test_update_flows():
    # NOTES:
    # - When a revision is installed from a remote it takes the date from the remote, not
    # updating the date to the current time
    # - If we want to install the revision and create it with a new date use --update-date
    # (name to be decided)
    # - Revisions are considered inmutable: if for example we do a conan install --update of a
    # revision that is already in the cache, but has a newer date in the remote, we will not install
    # anything, just updating the date in the cache to the one in the remote, so if you want to
    # get what the remote has you have to re-install you will have to remove the local
    # package and install from server
    # - In conan 2.X no remote means search in all remotes

    liba = ConanFileReference.loads("liba/1.0.0")

    servers = OrderedDict()
    for index in range(3):
        servers[f"server{index + 1}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})

    users = {"server1": [("user", "password")],
             "server2": [("user", "password")],
             "server3": [("user", "password")]}

    client = TestClient(servers=servers, users=users)
    client2 = TestClient(servers=servers, users=users)

    # create a revision 0 in client2, client2 will have an older revision than all the servers
    client2.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new revision 0")})
    client2.run("create .")

    # other revision created in client
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0")})
    client.run("create .")

    # we are patching the time all these revisions uploaded to the servers
    # will be older than the ones we create in local
    the_time = 0.0

    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    # upload other revision 1 we create in client
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new revision 1")})
    client.run("create .")
    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    # NOW WE HAVE:
    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # | REV1  (1020)| REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
    # | REV   (1010)|            | REV (10)   | REV (20)  | REV  (30)  |
    # |             |            |            |           |            |

    # 1. TESTING WITHOUT SPECIFIC REVISIONS AND WITH NO REMOTES: "conan install liba/1.0.0"

    # client2 already has a revision for this recipe, don't install anything
    client2.run("install liba/1.0.0@")
    assert "liba/1.0.0 from local cache - Cache" in client2.out
    assert "liba/1.0.0: Already installed!" in client2.out

    client.run("remove * -f")

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # |             | REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
    # |             |            | REV (10)   | REV (20)  | REV  (30)  |
    # |             |            |            |           |            |

    client.run("install liba/1.0.0@")

    # will not find revisions for the recipe -> search all remotes and install the
    # latest revision between all of them, in 2.0 no remotes means search in all of them
    # remote3 has the latest revision so we should pick that one
    # --> result: install rev from remote3
    assert "liba/1.0.0 from 'server3' - Downloaded" in client.out
    assert "liba/1.0.0: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" \
           " from remote 'server3'" in client.out

    latest_rrev = client.cache.get_latest_rrev(ConanFileReference.loads("liba/1.0.0@"))
    # check that we have stored REV1 in client with the same date from the server3
    assert client.cache.get_timestamp(latest_rrev) == the_time

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # |REV1 (60)    | REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
    # |             |            | REV (10)   | REV (20)  | REV  (30)  |
    # |             |            |            |           |            |

    client.run("install liba/1.0.0@ --update")
    # It will first check all the remotes and
    # will find the latest revision: REV1 from server3
    # --> result: we already have the revision installed so do nothing
    assert "liba/1.0.0 from 'server3' - Cache" in client.out
    assert "liba/1.0.0: Already installed!" in client.out

    # we create a newer revision in client
    client.run("remove * -f")
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new revision 2")})
    client.run("create .")

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # | REV2 (2000) | REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
    # |             |            | REV (10)   | REV (20)  | REV  (30)  |
    # |             |            |            |           |            |

    client.run("install liba/1.0.0@")
    # we already have a revision for liba/1.0.0 so don't install anything
    # --> result: don't install anything
    assert "liba/1.0.0: Already installed!" in client.out

    client.run("install liba/1.0.0@ --update")
    # we already have a newer revision in the client
    # we will check all the remotes, find the latest revision
    # this revision will be oldest than the one in the cache
    # --> result: don't install anything
    assert "liba/1.0.0 from local cache - Newer" in client.out
    assert "liba/1.0.0: Already installed!" in client.out

    # create newer revisions in servers so that the ones from the clients are older
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new rev in servers")})
    client.run("create .")
    rev_to_upload = client.cache.get_latest_rrev(liba)
    the_time = 2000000000.0
    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload {rev_to_upload.full_str()} -r server{index + 1} --all -c")

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # | REV2 (2000) | REV0 (1000)| REV3(2010) | REV3(2020)| REV3 (2030)|
    # |             |            | REV1(40)   | REV1(50)  | REV1 (60)  |
    # |             |            | REV (10)   | REV (20)  | REV  (30)  |
    # |             |            |            |           |            |

    client2.run("install liba/1.0.0@ --update")
    # now check for newer references with --update for client2 that has an older revision
    # when we use --update: first check all remotes (no -r argument) get latest revision
    # check if it is in cache, if it is --> stop, if it is not --> check date and install
    # --> result: install rev from server3
    assert "liba/1.0.0 from 'server3' - Updated" in client2.out
    assert f"liba/1.0.0: Downloaded recipe revision {rev_to_upload.revision}" in client2.out
    assert "liba/1.0.0: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" \
           " from remote 'server3'" in client2.out

    assert client2.cache.get_timestamp(rev_to_upload) == the_time

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # | REV2 (2000) | REV3 (2030)| REV3(2010) | REV3(2020)| REV3 (2030)|
    # |             | REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
    # |             |            | REV (10)   | REV (20)  | REV  (30)  |
    # |             |            |            |           |            |

    # TESTING WITH SPECIFIC REVISIONS AND WITH NO REMOTES: "conan install liba/1.0.0#rrev"
    # - In conan 2.X no remote means search in all remotes

    # check one revision we already have will not be installed
    # we search for that revision in the cache, we found it
    # --> result: don't install that
    latest_rrev = client.cache.get_latest_rrev(liba)
    client.run(f"install {latest_rrev}@#{latest_rrev.revision}")
    assert "liba/1.0.0 from 'server1' - Cache" in client.out
    assert "liba/1.0.0: Already installed!" in client.out

    client.run("remove * -f")

    client.run("remove '*' -f -r server1")
    client.run("remove '*' -f -r server2")
    client.run("remove '*' -f -r server3")

    # create new older revisions in servers
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("older rev in servers")})
    client.run("create .")
    server_rrev = client.cache.get_latest_rrev(liba)
    the_time = 0.0
    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload liba/1.0.0 -r server{index + 1} --all -c")

    client.run("remove * -f")

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # |             | REV3 (2030)| REV4(10)   | REV4(20)  | REV4 (30)  |
    # |             | REV0 (1000)|            |           |            |
    # |             |            |            |           |            |

    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("newer rev cache")})
    client.run("create .")

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # | REV5 (2001) | REV3 (2030)| REV4(10)   | REV4(20)  | REV4 (30)  |
    # |             | REV0 (1000)|            |           |            |
    # |             |            |            |           |            |

    # install REV4
    client.run(f"install {server_rrev}@#{server_rrev.revision}")
    # have a newer different revision in the cache, but ask for an specific revision that is in
    # the servers, will try to find that revision and install it from the first server found
    # will not check all the remotes for the latest because we consider revisions completely
    # inmutable so all of them are the same
    # --> result: install new revision asked, but the latest revision remains the other one, because
    # the one installed took the date from the server and it's older
    assert "liba/1.0.0: Not found in local cache, looking in remotes..." in client.out
    assert "liba/1.0.0: Checking all remotes: (server1, server2, server3)" in client.out
    assert "liba/1.0.0: Checking remote: server1" in client.out
    assert "liba/1.0.0: Checking remote: server2" not in client.out
    assert "liba/1.0.0: Checking remote: server3" not in client.out
    assert "liba/1.0.0: Trying with 'server1'..." in client.out
    latest_cache_revision = client.cache.get_latest_rrev(server_rrev.copy_clear_rev())
    assert latest_cache_revision != server_rrev

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # | REV5 (2001) | REV3 (2030)| REV4(10)   | REV4(20)  | REV4 (30)  |
    # | REV4 (30)   | REV0 (1000)|            |           |            |
    # |             |            |            |           |            |

    # TODO: add last test but with --update

    client.run("remove * -f")
    client.run("remove '*' -f -r server1")
    client.run("remove '*' -f -r server2")
    client.run("remove '*' -f -r server3")

    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new case")})
    client.run("create .")
    server_rrev = client.cache.get_latest_rrev(liba)
    the_time = time.time() + 10
    for index in range(3):
        the_time = the_time + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run(f"upload {server_rrev.full_str()} -r server{index + 1} --all -c")

    latest_server_time = the_time

    # | CLIENT      | CLIENT2    | SERVER1    | SERVER2   | SERVER3    |
    # |-------------|------------|------------|-----------|------------|
    # | REV6(2002)  | REV3 (2030)| REV6(2003) |REV6(2004) | REV6(2005) |
    # |             | REV0 (1000)|            |           |            |
    # |             |            |            |           |            |

    client.run(f"install {server_rrev}@#{server_rrev.revision} --update")

    # now we have the same revision with different dates in the servers and in the cache
    # in this case, if we specify --update we will check all the remotes, if that revision
    # has a newer date in the servers we will take that date from the server but we will not
    # install anything, we are considering revisions fully inmutable in 2.0
    # --> results: update revision date in cache, do not install anything

    latest_rrev_cache = client.cache.get_latest_rrev(liba)
    assert latest_server_time == client.cache.get_timestamp(latest_rrev_cache)

    # TODO: implement date update and checks in this case

    # --update
    # now in server: older revisions
    # in cache: we have the revision from the servers installed but it's not the latest
    # --> result: don't install the revision from servers

    client.run("remove * -f")

    # re-create the last one we uploaded to the servers so that it has newer date
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("new case")})
    client.run("create .")

    # create a new revision in cache that will be the latest
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("this is the latest")})
    client.run("create .")

    cache_revisions = client.cache.get_recipe_revisions(liba)

    # try to install the one from the servers
    client.run(f"install {server_rrev}@#{server_rrev.revision} --update")
    # TODO: implement checks in this case


def test_update_flows_version_ranges():
    pass
