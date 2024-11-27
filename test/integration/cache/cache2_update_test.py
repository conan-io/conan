import copy
from collections import OrderedDict

import pytest
from mock import patch

from conans.model.recipe_ref import RecipeReference
from conans.server.revision_list import RevisionList
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID


class TestUpdateFlows:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.liba = RecipeReference.loads("liba/1.0.0")

        servers = OrderedDict()
        for index in range(3):
            servers[f"server{index}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})

        self.client = TestClient(servers=servers, inputs=3*["user", "password"])
        self.client2 = TestClient(servers=servers, inputs=3*["user", "password"])
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
            client.run(f"upload {ref} -r {remote} -c")

    def test_revision_fixed_version(self):
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

        # 1. TESTING WITHOUT SPECIFIC REVISIONS AND WITH NO REMOTES: "conan install --requires=liba/1.0.0"

        # client2 already has a revision for this recipe, don't install anything
        self.client2.run("install --requires=liba/1.0.0@")
        self.client2.assert_listed_require({"liba/1.0.0": "Cache"})
        assert "liba/1.0.0: Already installed!" in self.client2.out

        self.client.run("remove * -c")

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |             | REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        self.client.run("install --requires=liba/1.0.0@")

        # will not find revisions for the recipe -> search remotes by order and install the
        # first match that is rev1 from server0
        # --> result: install rev from server0
        self.client.assert_listed_require({"liba/1.0.0": "Downloaded (server0)"})
        assert f"liba/1.0.0: Retrieving package {NO_SETTINGS_PACKAGE_ID}" \
               " from remote 'server0'" in self.client.out

        latest_rrev = self.client.cache.get_latest_recipe_reference(RecipeReference.loads("liba/1.0.0@"))
        # check that we have stored REV1 in client with the same date from the server0
        assert latest_rrev.timestamp == self.server_times["server0"]
        assert latest_rrev.timestamp == self.server_times["server0"]

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |REV1 (40)    | REV0 (1000)| REV1(40)   | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        self.client.run("install --requires=liba/1.0.0@ --update")
        # It will first check all the remotes and
        # will find the latest revision: REV1 from server2 we already have that
        # revision but the date is newer
        # --> result: do not download anything, but update REV1 date in cache
        self.client.assert_listed_require({"liba/1.0.0": "Cache (Updated date) (server2)"})
        assert "liba/1.0.0: Already installed!" in self.client.out

        # now create a newer REV2 in server2 and if we do --update it should update the date
        # to the date in server0 and associate that remote but not install anything

        # we create a newer revision in client2
        self.client2.run("remove * -c")
        self.client2.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV2")})
        self.client2.run("create .")

        self.the_time = 100.0

        self._upload_ref_to_server("liba/1.0.0", "server2", self.client2)

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |REV1 (60)    | REV2 (1000)| REV1(100)  | REV1(50)  | REV2 (100) |
        # |             |            | REV (10)   | REV (20)  | REV1 (60)  |
        # |             |            |            |           | REV  (30)  |

        self.client.run("install --requires=liba/1.0.0@ --update")
        # --> result: Update date and server because server0 has a newer date
        latest_rrev = self.client.cache.get_latest_recipe_reference(self.liba)
        self.client.assert_listed_require({"liba/1.0.0": "Updated (server2)"})
        assert "liba/1.0.0: Downloaded package" in self.client.out
        assert latest_rrev.timestamp == self.server_times["server2"]

        # we create a newer revision in client
        self.client.run("remove * -c")
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV2")})
        self.client.run("create .")
        self.client.run(f"remove {latest_rrev.repr_notime()} -c -r server2")

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |REV2 (2002)  | REV2 (2000)| REV1(100)  | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV (30)   |
        # |             |            |            |           |            |

        self.client.run("install --requires=liba/1.0.0@")
        # we already have a revision for liba/1.0.0 so don't install anything
        # --> result: don't install anything
        assert "liba/1.0.0: Already installed!" in self.client.out

        self.client.run("install --requires=liba/1.0.0@ --update")
        # we already have a newer revision in the client
        # we will check all the remotes, find the latest revision
        # this revision will be oldest than the one in the cache
        # --> result: don't install anything
        self.client.assert_listed_require({"liba/1.0.0": "Newer"})
        assert "liba/1.0.0: Already installed!" in self.client.out

        # create newer revisions in servers so that the ones from the clients are older
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV3")})
        self.client.run("create .")
        rev_to_upload = self.client.cache.get_latest_recipe_reference(self.liba)
        # the future
        self.the_time = 3000000000.0
        self._upload_ref_to_all_servers(repr(rev_to_upload), self.client)

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV2 (2002) | REV2 (2000)| REV3(3010) | REV3(3020)| REV3 (3030)|
        # |             |            | REV1(100)  | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        self.client2.run("install --requires=liba/1.0.0@ --update")
        # now check for newer references with --update for client2 that has an older revision
        # when we use --update: first check all remotes (no -r argument) get latest revision
        # check if it is in cache, if it is --> stop, if it is not --> check date and install
        # --> result: install rev from server2
        self.client2.assert_listed_require({"liba/1.0.0": "Updated (server2)"})
        assert f"liba/1.0.0: Downloaded recipe revision {rev_to_upload.revision}" in self.client2.out
        assert f"liba/1.0.0: Retrieving package {NO_SETTINGS_PACKAGE_ID}" \
               " from remote 'server2'" in self.client2.out

        check_ref = RecipeReference.loads(str(rev_to_upload))  # without revision
        rev_to_upload = self.client2.cache.get_latest_recipe_reference(check_ref)
        assert rev_to_upload.timestamp == self.server_times["server2"]

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV2 (2000) | REV3 (3030)| REV3(3010) | REV3(3020)| REV3 (3030)|
        # |             | REV0 (1000)| REV1(100)  | REV1(50)  | REV1 (60)  |
        # |             |            | REV (10)   | REV (20)  | REV  (30)  |
        # |             |            |            |           |            |

        # TESTING WITH SPECIFIC REVISIONS AND WITH NO REMOTES: "conan install --requires=liba/1.0.0#rrev"
        # - In conan 2.X no remote means search in all remotes

        # check one revision we already have will not be installed
        # we search for that revision in the cache, we found it
        # --> result: don't install that
        latest_rrev = self.client.cache.get_latest_recipe_reference(self.liba)
        self.client.run(f"install --requires={latest_rrev}@#{latest_rrev.revision}")
        self.client.assert_listed_require({"liba/1.0.0": "Cache"})
        assert "liba/1.0.0: Already installed!" in self.client.out

        self.client.run("remove * -c")

        self.client.run("remove '*' -c -r server0")
        self.client.run("remove '*' -c -r server1")
        self.client.run("remove '*' -c -r server2")

        # create new older revisions in servers
        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV4")})
        self.client.run("create .")
        server_rrev = self.client.cache.get_latest_recipe_reference(self.liba)
        self.the_time = 0.0

        self._upload_ref_to_all_servers("liba/1.0.0", self.client)

        self.client.run("remove * -c")

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
        self.client.run(f"install --requires={server_rrev}@#{server_rrev.revision}")
        # have a newer different revision in the cache, but ask for an specific revision that is in
        # the servers, will try to find that revision and install it from the first server found
        # will not check all the remotes for the latest because we consider revisions completely
        # immutable so all of them are the same
        # --> result: install new revision asked, but the latest revision remains the other one,
        # because the one installed took the date from the server and it's older
        assert "liba/1.0.0: Not found in local cache, looking in remotes..." in self.client.out
        assert "liba/1.0.0: Checking remote: server0" in self.client.out
        assert "liba/1.0.0: Checking remote: server1" not in self.client.out
        assert "liba/1.0.0: Checking remote: server2" not in self.client.out
        server_rrev_norev = copy.copy(server_rrev)
        server_rrev_norev.revision = None
        latest_cache_revision = self.client.cache.get_latest_recipe_reference(server_rrev_norev)
        assert latest_cache_revision != server_rrev

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV5 (2001) | REV3 (3030)| REV4(10)   | REV4(20)  | REV4 (30)  |
        # | REV4 (10)   | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.run(f"install --requires={server_rrev}@#{server_rrev.revision} --update")
        # last step without --update it took the REV4 from server0 but now
        # we tell conan to search for newer recipes of an specific revision
        # it will go to server2 and update the local date with the one
        # from the remote
        # --> result: update REV4 date to 30 but it won't be latest

        latest_cache_revision = self.client.cache.get_latest_recipe_reference(server_rrev_norev)
        assert latest_cache_revision != server_rrev
        latest_cache_revision = self.client.cache.recipe_layout(server_rrev).reference

        assert self.the_time == latest_cache_revision.timestamp
        self.client.assert_listed_require({"liba/1.0.0": "Cache (Updated date) (server2)"})

        self.client.run("remove * -c")
        self.client.run("remove '*' -c -r server0")
        self.client.run("remove '*' -c -r server1")
        self.client.run("remove '*' -c -r server2")

        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV6")})
        self.client.run("create .")
        server_rrev = self.client.cache.get_latest_recipe_reference(self.liba)
        self.the_time = 3000000020.0

        self._upload_ref_to_all_servers(repr(server_rrev), self.client)

        latest_server_time = self.the_time

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV6(2002)  | REV3 (3030)| REV6(3030) |REV6(3040) | REV6(3050) |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.run(f"install --requires={server_rrev}@#{server_rrev.revision} --update")

        # now we have the same revision with different dates in the servers and in the cache
        # in this case, if we specify --update we will check all the remotes, if that revision
        # has a newer date in the servers we will take that date from the server but we will not
        # install anything, we are considering revisions fully immutable in 2.0
        # --> results: update revision date in cache, do not install anything

        latest_rrev_cache = self.client.cache.get_latest_recipe_reference(self.liba)
        assert latest_server_time == latest_rrev_cache.timestamp
        self.client.assert_listed_require({"liba/1.0.0": "Cache (Updated date) (server2)"})

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV6(2002)  | REV3 (3050)| REV6(3030) |REV6(3040) | REV6(3050) |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.run("remove * -c")

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # |             | REV3 (3050)| REV6(3030) |REV6(3040) | REV6(3050) |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

        self.client.run(f"install --requires={server_rrev}@#{server_rrev.revision} --update")

        # now we have the same revision with different dates in the servers and in the cache
        # in this case, if we specify --update we will check all the remotes and will install
        # the revision from the server that has the latest date
        # --> results: install from server2

        latest_rrev_cache = self.client.cache.get_latest_recipe_reference(self.liba)
        assert latest_server_time == latest_rrev_cache.timestamp
        self.client.assert_listed_require({"liba/1.0.0": "Downloaded (server2)"})

        # | CLIENT      | CLIENT2    | SERVER0    | SERVER1   | SERVER2    |
        # |-------------|------------|------------|-----------|------------|
        # | REV6(3050)  | REV3 (3050)| REV6(3030) |REV6(3040) | REV6(3050) |
        # |             | REV0 (1000)|            |           |            |
        # |             |            |            |           |            |

    def test_version_ranges(self):
        # create a revision 0 in client2, client2 will have an older revision than all the servers
        for minor in range(3):
            self.client2.save({"conanfile.py": GenConanfile("liba", f"1.{minor}.0").with_build_msg("REV0")})
            self.client2.run("create .")
            self.the_time = 10.0 + minor*10.0
            self._upload_ref_to_server(f"liba/1.{minor}.0", f"server{minor}", self.client2)

        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV0")})
        self.client.run("create .")

        # NOW WE HAVE:
        # | CLIENT         | CLIENT2        | SERVER0        | SERVER1        | SERVER2        |
        # |----------------|----------------|----------------|----------------|----------------|
        # | 1.0 REV0 (1000)| 1.0 REV0 (1000)| 1.0 REV0 (10)  | 1.1 REV0 (10)  | 1.2 REV0 (10)  |
        # |                | 1.1 REV0 (1000)|                |                |                |
        # |                | 1.2 REV0 (1000)|                |                |                |

        self.client.run("install --requires=liba/[>0.9.0]@")
        assert "liba/[>0.9.0]: liba/1.0.0" in self.client.out
        assert "liba/1.0.0: Already installed!" in self.client.out

        self.client.run("remove * -c")

        # | CLIENT         | CLIENT2        | SERVER0        | SERVER1        | SERVER2        |
        # |----------------|----------------|----------------|----------------|----------------|
        # |                | 1.0 REV0 (1000)| 1.0 REV0 (10)  | 1.1 REV0 (20)  | 1.2 REV0 (30)  |
        # |                | 1.1 REV0 (1000)|                |                |                |
        # |                | 1.2 REV0 (1000)|                |                |                |

        self.client.run("install --requires=liba/[>0.9.0]@")

        # will not find versions for the recipe in cache -> search remotes by order and install the
        # first match that is 1.0 from server0
        # --> result: install 1.0 from server0
        assert "liba/[>0.9.0]: liba/1.0.0" in self.client.out
        self.client.assert_listed_require({"liba/1.0.0": "Downloaded (server0)"})

        latest_rrev = self.client.cache.get_latest_recipe_reference(RecipeReference.loads("liba/1.0.0@"))
        assert latest_rrev.timestamp == self.server_times["server0"]

        # | CLIENT         | CLIENT2        | SERVER0        | SERVER1        | SERVER2        |
        # |----------------|----------------|----------------|----------------|----------------|
        # | 1.0 REV0 (10)| 1.0 REV0 (1000)  | 1.0 REV0 (10)  | 1.1 REV0 (20)  | 1.2 REV0 (30)  |
        # |                | 1.1 REV0 (1000)|                |                |                |
        # |                | 1.2 REV0 (1000)|                |                |                |

        self.client.run("install --requires=liba/[>1.0.0]@")
        # first match that is 1.1 from server1
        # --> result: install 1.1 from server1
        assert "liba/[>1.0.0]: liba/1.1.0" in self.client.out
        self.client.assert_listed_require({"liba/1.1.0": "Downloaded (server1)"})

        # | CLIENT         | CLIENT2        | SERVER0        | SERVER1        | SERVER2        |
        # |----------------|----------------|----------------|----------------|----------------|
        # | 1.1 REV0 (10)  | 1.0 REV0 (1000)| 1.0 REV0 (10)  | 1.1 REV0 (20)  | 1.2 REV0 (30)  |
        # |                | 1.1 REV0 (1000)|                |                |                |
        # |                | 1.2 REV0 (1000)|                |                |                |

        self.client.run("install --requires=liba/[>1.0.0]@ --update")
        # check all servers
        # --> result: install 1.2 from server2
        assert "liba/[>1.0.0]: liba/1.2.0" in self.client.out
        self.client.assert_listed_require({"liba/1.2.0": "Downloaded (server2)"})

        # If we have multiple revisions with different names for the same version and we
        # do a --update we are going to first resolver the version range agains server0
        # then in the proxy we will install rev2 that is the latest
        # | CLIENT         | CLIENT2        | SERVER0        | SERVER1        | SERVER2        |
        # |----------------|----------------|----------------|----------------|----------------|
        # | 1.0 REV0 (10)  |                | 1.2 REV0 (10)  | 1.2 REV1 (20)  | 1.2 REV2 (30)  |
        # |                |                |                |                |                |
        # |                |                |                |                |                |

        self.client.run("remove * -c")
        self.client2.run("remove * -c")

        # now we are uploading different revisions with different dates, but the same version
        for minor in range(3):
            self.client2.save({"conanfile.py": GenConanfile("liba", f"1.2.0").with_build_msg(f"REV{minor}")})
            self.client2.run("create .")
            self.the_time = 10.0 + minor*10.0
            self._upload_ref_to_server(f"liba/1.2.0", f"server{minor}", self.client2)

        self.client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_build_msg("REV0")})
        self.client.run("create .")

        self.client.run("install --requires=liba/[>1.0.0]@ --update")
        assert "liba/[>1.0.0]: liba/1.2.0" in self.client.out
        self.client.assert_listed_require({"liba/1.2.0": "Downloaded (server2)"})
        assert f"liba/1.2.0: Retrieving package {NO_SETTINGS_PACKAGE_ID} " \
               "from remote 'server2' " in self.client.out


@pytest.mark.parametrize("update,result", [
                                           # Not a real pattern, works to support legacy syntax
                                           ["*", {"liba/1.1": "Downloaded (default)",
                                                  "libb/1.1": "Downloaded (default)"}],
                                           ["libc", {"liba/1.0": "Cache",
                                                     "libb/1.0": "Cache"}],
                                           ["liba", {"liba/1.1": "Downloaded (default)",
                                                       "libb/1.0": "Cache"}],
                                           ["libb", {"liba/1.0": "Cache",
                                                       "libb/1.1": "Downloaded (default)"}],
                                           ["", {"liba/1.0": "Cache",
                                                 "libb/1.0": "Cache"}],
                                           # Patterns not supported, only full name match
                                           ["lib*", {"liba/1.0": "Cache",
                                                     "libb/1.0": "Cache"}],
                                           ["liba/*", {"liba/1.0": "Cache",
                                                       "libb/1.0": "Cache"}],
                                           # None only passes legacy --update without args,
                                           # to ensure it works, it should be the same as passing *
                                           [None, {"liba/1.1": "Downloaded (default)",
                                                   "libb/1.1": "Downloaded (default)"}]
                                           ])
def test_muliref_update_pattern(update, result):
    tc = TestClient(light=True, default_server_user=True)
    tc.save({"liba/conanfile.py": GenConanfile("liba"),
             "libb/conanfile.py": GenConanfile("libb")})
    tc.run("create liba --version=1.0")
    tc.run("create libb --version=1.0")

    tc.run("create liba --version=1.1")
    tc.run("create libb --version=1.1")

    tc.run("upload * -c -r default")
    tc.run('remove "*/1.1" -c')

    update_flag = f"--update={update}" if update is not None else "--update"

    tc.run(f'install --requires="liba/[>=1.0]" --requires="libb/[>=1.0]" -r default {update_flag}')

    tc.assert_listed_require(result)
