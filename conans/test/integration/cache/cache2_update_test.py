from collections import OrderedDict

import pytest
from mock import patch

from conans.model.ref import ConanFileReference
from conans.server.revision_list import RevisionList
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


class TestUpdateFlows:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.liba = ConanFileReference.loads("liba/1.0.0")

        servers = OrderedDict()
        for index in range(3):
            servers[f"server{index}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})

        users = {"server0": [("user", "password")],
                 "server1": [("user", "password")],
                 "server2": [("user", "password")]}

        self.client = TestClient(servers=servers, users=users)
        self.client2 = TestClient(servers=servers, users=users)
        self.the_time = 0.0
        self.server_times = {}

    def _upload_ref_to_all_servers(self, ref, client):
        # we are patching the time all these revisions uploaded to the servers
        # will be older than the ones we create in local
        for index in range(3):
            self.the_time = self.the_time + 10
            self._upload_ref_to_server(ref, f"server{index}", client)

    def _upload_ref_to_server(self, ref, remote, client):
        # we are patching the time all these revisions uploaded to the servers
        # will be older than the ones we create in local
        self.server_times[remote] = self.the_time
        with patch.object(RevisionList, '_now', return_value=self.the_time):
            client.run(f"upload {ref} -r {remote} --all -c")

    def test_update_flows(self):
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

        # create a revision 0 in client2, client2 will have an older revision than all the servers
        self.client2.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV0")})
        self.client2.run("create .")

        # other revision created in client
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV")})
        self.client.run("create .")

        self._upload_ref_to_all_servers("liba/1.0.0", self.client)

        # upload other revision 1 we create in client
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV1")})
        self.client.run("create .")

        self._upload_ref_to_all_servers("liba/1.0.0", self.client)

        # NOW WE HAVE:
        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV1  (1020)| REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
        # | REV   (1010)|            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        # 1. TESTING WITHOUT SPECIFIC REVISIONS AND WITH NO REMOTES: "conan install liba/1.0.0"

        # client2 already has a revision for this recipe, don't install anything
        self.client2.run("install liba/1.0.0@")
        assert "liba/1.0.0 from local cache - Cache" in self.client2.out
        assert "liba/1.0.0: Already installed!" in self.client2.out

        self.client.run("remove * -f")

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |             | REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        self.client.run("install liba/1.0.0@")

        # will not find revisions for the recipe -> search remotes by order and install the
        # first match that is rev1 from server0
        # --> result: install rev from server0
        assert "liba/1.0.0 from 'server0' - Downloaded" in self.client.out
        assert "liba/1.0.0: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" \
               " from remote 'server0'" in self.client.out

        latest_rrev = self.client.cache.get_latest_rrev(ConanFileReference.loads("liba/1.0.0@"))
        # check that we have stored REV1 in client with the same date from the server0
        assert self.client.cache.get_timestamp(latest_rrev) == self.server_times["server0"]

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |REV1 (40)    | REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        self.client.run("install liba/1.0.0@ --update")
        # It will first check all the remotes and
        # will find the latest revision: REV1 from server2 we already have that
        # revision but the date is newer
        # --> result: do not download anything, but update REV1 date in cache
        assert "liba/1.0.0 from 'server2' - Cache (Updated date)" in self.client.out
        assert "liba/1.0.0: Already installed!" in self.client.out

        # now create a newer REV2 in server2 and if we do --update it should update the date
        # to the date in server0 and associate that remote but not install anything

        # we create a newer revision in client2
        self.client2.run("remove * -f")
        self.client2.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV2")})
        self.client2.run("create .")

        self.the_time = 100.0

        self._upload_ref_to_server("liba/1.0.0", "server2", self.client2)

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |REV1 (60)    | REV2 (1000)| REV1(100)  | REV1(50)  | REV2 (100) |
        # |             |            | REV (10)   | REV (20)  | REV1 (60)  |
        # |             |            |            |           | REV  (30)  |

        self.client.run("install liba/1.0.0@ --update")
        # --> result: Update date and server because server0 has a newer date
        latest_rrev = self.client.cache.get_latest_rrev(self.liba)
        assert "liba/1.0.0 from 'server2' - Updated" in self.client.out
        assert "liba/1.0.0: Downloaded package revision cf924fbb5ed463b8bb960cf3a4ad4f3a" in self.client.out
        assert self.client.cache.get_timestamp(latest_rrev) == self.server_times["server2"]

        # we create a newer revision in client
        self.client.run("remove * -f")
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV2")})
        self.client.run("create .")
        self.client.run(f"remove {latest_rrev.full_str()} -f -r server2")

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |REV2 (2002)  | REV2 (2000)| REV1(100)  | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV (30)   |
        # |             |            |            |           |            |

        self.client.run("install liba/1.0.0@")
        # we already have a revision for liba/1.0.0 so don't install anything
        # --> result: don't install anything
        assert "liba/1.0.0: Already installed!" in self.client.out

        self.client.run("install liba/1.0.0@ --update")
        # we already have a newer revision in the client
        # we will check all the remotes, find the latest revision
        # this revision will be oldest than the one in the cache
        # --> result: don't install anything
        assert "liba/1.0.0 from local cache - Newer" in self.client.out
        assert "liba/1.0.0: Already installed!" in self.client.out

        # create newer revisions in servers so that the ones from the clients are older
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV3")})
        self.client.run("create .")
        rev_to_upload = self.client.cache.get_latest_rrev(self.liba)
        # the future
        self.the_time = 3000000000.0
        self._upload_ref_to_all_servers(rev_to_upload.full_str(), self.client)

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV2 (2002) | REV2 (2000)| REV3(3010) | REV3(3020)| REV3 (3030)|
        # |             |            | REV1(100)  | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        self.client2.run("install liba/1.0.0@ --update")
        # now check for newer references with --update for client2 that has an older revision
        # when we use --update: first check all remotes (no -r argument) get latest revision
        # check if it is in cache, if it is --> stop, if it is not --> check date and install
        # --> result: install rev from server2
        assert "liba/1.0.0 from 'server2' - Updated" in self.client2.out
        assert f"liba/1.0.0: Downloaded recipe revision {rev_to_upload.revision}" in self.client2.out
        assert "liba/1.0.0: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" \
               " from remote 'server2'" in self.client2.out

        assert self.client2.cache.get_timestamp(rev_to_upload) == self.server_times["server2"]

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV2 (2000) | REV3 (3030)| REV3(3010) | REV3(3020)| REV3 (3030)|
        # |             | REV0 (1000)| REV1(100)  | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        # TESTING WITH SPECIFIC REVISIONS AND WITH NO REMOTES: "conan install liba/1.0.0#rrev"
        # - In conan 2.X no remote means search in all remotes

        # check one revision we already have will not be installed
        # we search for that revision in the cache, we found it
        # --> result: don't install that
        latest_rrev = self.client.cache.get_latest_rrev(self.liba)
        self.client.run(f"install {latest_rrev}@#{latest_rrev.revision}")
        assert "liba/1.0.0 from 'server0' - Cache" in self.client.out
        assert "liba/1.0.0: Already installed!" in self.client.out

        self.client.run("remove * -f")

        self.client.run("remove '*' -f -r server0")
        self.client.run("remove '*' -f -r server1")
        self.client.run("remove '*' -f -r server2")

        # create new older revisions in servers
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV4")})
        self.client.run("create .")
        server_rrev = self.client.cache.get_latest_rrev(self.liba)
        self.the_time = 0.0

        self._upload_ref_to_all_servers("liba/1.0.0", self.client)

        self.client.run("remove * -f")

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |             | REV3 (3030)| REV4(10)   | REV4(20)  | REV4 (30)  |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV5")})
        self.client.run("create .")

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV5 (2001) | REV3 (3030)| REV4(10)   | REV4(20)  | REV4 (30)  |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        # install REV4
        self.client.run(f"install {server_rrev}@#{server_rrev.revision}")
        # have a newer different revision in the cache, but ask for an specific revision that is in
        # the servers, will try to find that revision and install it from the first server found
        # will not check all the remotes for the latest because we consider revisions completely
        # immutable so all of them are the same
        # --> result: install new revision asked, but the latest revision remains the other one,
        # because the one installed took the date from the server and it's older
        assert "liba/1.0.0: Not found in local cache, looking in remotes..." in self.client.out
        assert "liba/1.0.0: Checking all remotes: (server0, server1, server2)" in self.client.out
        assert "liba/1.0.0: Checking remote: server0" in self.client.out
        assert "liba/1.0.0: Checking remote: server1" not in self.client.out
        assert "liba/1.0.0: Checking remote: server2" not in self.client.out
        assert "liba/1.0.0: Trying with 'server0'..." in self.client.out
        latest_cache_revision = self.client.cache.get_latest_rrev(server_rrev.copy_clear_rev())
        assert latest_cache_revision != server_rrev

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV5 (2001) | REV3 (3030)| REV4(10)   | REV4(20)  | REV4 (30)  |
        # | REV4 (10)   | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.run(f"install {server_rrev}@#{server_rrev.revision} --update")
        # last step without --update it took the REV4 from server0 but now
        # we tell conan to search for newer recipes of an specific revision
        # it will go to server2 and update the local date with the one
        # from the remote
        # --> result: update REV4 date to 30 but it won't be latest

        latest_cache_revision = self.client.cache.get_latest_rrev(server_rrev.copy_clear_rev())
        assert latest_cache_revision != server_rrev
        assert self.the_time == self.client.cache.get_timestamp(server_rrev)
        assert "liba/1.0.0 from 'server2' - Cache (Updated date)" in self.client.out

        self.client.run("remove * -f")
        self.client.run("remove '*' -f -r server0")
        self.client.run("remove '*' -f -r server1")
        self.client.run("remove '*' -f -r server2")

        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV6")})
        self.client.run("create .")
        server_rrev = self.client.cache.get_latest_rrev(self.liba)
        self.the_time = 3000000020.0

        self._upload_ref_to_all_servers(server_rrev.full_str(), self.client)

        latest_server_time = self.the_time

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV6(2002)  | REV3 (3030)| REV6(3030) |REV6(3040) | REV6(3050) |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.run(f"install {server_rrev}@#{server_rrev.revision} --update")

        # now we have the same revision with different dates in the servers and in the cache
        # in this case, if we specify --update we will check all the remotes, if that revision
        # has a newer date in the servers we will take that date from the server but we will not
        # install anything, we are considering revisions fully immutable in 2.0
        # --> results: update revision date in cache, do not install anything

        latest_rrev_cache = self.client.cache.get_latest_rrev(self.liba)
        assert latest_server_time == self.client.cache.get_timestamp(latest_rrev_cache)
        assert "liba/1.0.0 from 'server2' - Cache (Updated date)" in self.client.out

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV6(2002)  | REV3 (3050)| REV6(3030) |REV6(3040) | REV6(3050) |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.run("remove * -f")

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |             | REV3 (3050)| REV6(3030) |REV6(3040) | REV6(3050) |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.run(f"install {server_rrev}@#{server_rrev.revision} --update")

        # now we have the same revision with different dates in the servers and in the cache
        # in this case, if we specify --update we will check all the remotes and will install
        # the revision from the server that has the latest date
        # --> results: install from server2

        latest_rrev_cache = self.client.cache.get_latest_rrev(self.liba)
        assert latest_server_time == self.client.cache.get_timestamp(latest_rrev_cache)
        assert "liba/1.0.0 from 'server2' - Downloaded" in self.client.out

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV6(3050)  | REV3 (3050)| REV6(3030) |REV6(3040) | REV6(3050) |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

    def test_update_flows_version_ranges(self):
        pass
