import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.scm import create_local_git_repo
from conan.test.utils.tools import TestClient


@pytest.mark.tool("git")
class TestGitRemotesBasic:

    def test_basic_resolution_from_git(self):
        """Package not in cache: git= on require clones and exports it"""
        repo_url, _ = create_local_git_repo({"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11", git=repo_url)})
        c.run("install . --build=missing")
        assert "resolving from git remote" in c.out
        assert "zlib/1.2.11" in c.out

    def test_cache_first_no_reclone_on_second_run(self):
        """Second install reuses cache — no re-clone"""
        repo_url, _ = create_local_git_repo({"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11", git=repo_url)})
        c.run("install . --build=missing")
        assert "resolving from git remote" in c.out

        c.run("install . --build=missing")
        assert "Found in cache (configured via git remote" in c.out
        assert "Cloning" not in c.out

    def test_update_flag_forces_reclone(self):
        """--update forces a re-clone from git"""
        repo_url, _ = create_local_git_repo({"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11", git=repo_url)})
        c.run("install . --build=missing")
        c.run("install . --build=missing --update")
        assert "Updating from git remote" in c.out
        assert "Cloning" in c.out


@pytest.mark.tool("git")
class TestGitRemotesRef:

    def test_branch_ref(self):
        """git= with @branch clones and checks out that branch"""
        repo_url, _ = create_local_git_repo({"conanfile.py": GenConanfile("mypkg", "1.0")},
                                            branch="dev")
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0", git=f"{repo_url}@dev")})
        c.run("install . --build=missing")
        assert "mypkg/1.0" in c.out
        assert "git ref: dev" in c.out

    def test_tag_ref(self):
        """git= with @tag clones and checks out that tag"""
        repo_url, _ = create_local_git_repo({"conanfile.py": GenConanfile("mypkg", "2.0")},
                                            tags=["v2.0"])
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/2.0",
                                                                git=f"{repo_url}@v2.0")})
        c.run("install . --build=missing")
        assert "mypkg/2.0" in c.out
        assert "git ref: v2.0" in c.out

    def test_commit_ref(self):
        """git= with @<sha> checks out that exact commit"""
        repo_url, commit = create_local_git_repo({"conanfile.py": GenConanfile("mypkg", "3.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/3.0",
                                                                git=f"{repo_url}@{commit}")})
        c.run("install . --build=missing")
        assert "mypkg/3.0" in c.out
        assert f"git ref: {commit}" in c.out


@pytest.mark.tool("git")
class TestGitRemotesRequireTypes:

    @pytest.mark.parametrize("method", [
        "with_requirement",  # self.requires(git=)      — host dependency
        "with_tool_requirement",  # self.tool_requires(git=) — build-context tool
        "with_test_requirement",  # self.test_requires(git=) — test-only host dependency
    ])
    def test_git_resolution_by_require_type(self, method):
        """git= works for requires, tool_requires and test_requires"""
        repo_url, _ = create_local_git_repo({"conanfile.py": GenConanfile("mypkg", "1.0")})
        consumer = getattr(GenConanfile(), method)("mypkg/1.0", git=repo_url)
        c = TestClient(light=True)
        c.save({"conanfile.py": str(consumer)})
        c.run("install . --build=missing")
        assert "resolving from git remote" in c.out
        assert "mypkg/1.0" in c.out


@pytest.mark.tool("git")
class TestGitRemotesErrors:

    def test_missing_conanfile_in_repo(self):
        """Repo without conanfile.py gives a clear error message"""
        repo_url, _ = create_local_git_repo(files={"README.md": "# hello"})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11", git=repo_url)})
        c.run("install . --build=missing", assert_error=True)
        assert "conanfile.py not found" in c.out


@pytest.mark.tool("git")
class TestGitRemotesTransitive:

    def test_transitive_deps_both_from_git(self):
        """Pkg A from git= requires pkg B, which also has a git= entry in its conanfile"""
        repo_b_url, _ = create_local_git_repo({"conanfile.py": GenConanfile("pkgb", "1.0")})
        repo_a_url, _ = create_local_git_repo(
            files={"conanfile.py": GenConanfile("pkga", "1.0").with_requirement("pkgb/1.0",
                                                                                git=repo_b_url)}
        )
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("pkga/1.0", git=repo_a_url)})
        c.run("install . --build=missing")
        assert "pkga/1.0" in c.out
        assert "pkgb/1.0" in c.out
        assert c.out.count("resolving from git remote") == 2

    def test_diamond_all_from_git(self):
        """Diamond: consumer->pkga->pkgc and consumer->pkgb->pkgc, all in separate git repos.
        pkgc is cloned once (first encounter); the second encounter finds it already in cache."""
        # pkgc: leaf, no dependencies
        repo_c_url, _ = create_local_git_repo({"conanfile.py": GenConanfile("pkgc", "1.0")})
        # pkga and pkgb both depend on pkgc/1.0 via git=
        repo_a_url, _ = create_local_git_repo(
            files={"conanfile.py":  GenConanfile("pkga", "1.0").with_requirement("pkgc/1.0",
                                                                                 git=repo_c_url)}
        )
        repo_b_url, _ = create_local_git_repo(
            files={"conanfile.py": GenConanfile("pkgb", "1.0").with_requirement("pkgc/1.0",
                                                                                git=repo_c_url)}
        )
        # consumer depends on both pkga and pkgb
        c = TestClient(light=True)
        c.save({"conanfile.py": str(
            GenConanfile()
            .with_requirement("pkga/1.0", git=repo_a_url)
            .with_requirement("pkgb/1.0", git=repo_b_url))})
        c.run("install . --build=missing")
        assert "pkga/1.0" in c.out
        assert "pkgb/1.0" in c.out
        assert "pkgc/1.0" in c.out
        # pkga, pkgb, pkgc each cloned once from git (3 fresh resolutions)
        assert c.out.count("resolving from git remote") == 3
        # pkgc is found in cache the second time (via pkgb's requires, after pkga already exported it)
        assert c.out.count("Found in cache (configured via git remote") == 1
