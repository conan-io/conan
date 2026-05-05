import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.scm import create_local_git_repo
from conan.test.utils.tools import TestClient


def _header_lib(name, version):
    """Generate a header-only conanfile (no binary required)"""
    return str(GenConanfile(name, version).with_package_type("header-library"))


@pytest.mark.tool("git")
class TestGitRemotesBasic:

    def test_basic_resolution_from_git(self):
        """Package not in cache: profile git_remote entry clones and exports it"""
        repo_url, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("zlib", "1.2.11")}
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            zlib/1.2.11: {repo_url}
            """)
        c.save({
            "profile": profile,
            "conanfile.py": str(GenConanfile().with_requires("zlib/1.2.11")),
        })
        c.run("install . -pr=profile --build=missing")
        assert "resolving from git remote" in c.out
        assert "zlib/1.2.11" in c.out

    def test_cache_first_no_reclone_on_second_run(self):
        """Second install reuses cache — no re-clone"""
        repo_url, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("zlib", "1.2.11")}
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            zlib/1.2.11: {repo_url}
            """)
        c.save({
            "profile": profile,
            "conanfile.py": str(GenConanfile().with_requires("zlib/1.2.11")),
        })
        c.run("install . -pr=profile --build=missing")
        assert "resolving from git remote" in c.out

        c.run("install . -pr=profile --build=missing")
        assert "Found in cache (configured via git remote" in c.out
        assert "Cloning" not in c.out

    def test_update_flag_forces_reclone(self):
        """--update forces a re-clone from git"""
        repo_url, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("zlib", "1.2.11")}
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            zlib/1.2.11: {repo_url}
            """)
        c.save({
            "profile": profile,
            "conanfile.py": str(GenConanfile().with_requires("zlib/1.2.11")),
        })
        c.run("install . -pr=profile --build=missing")
        c.run("install . -pr=profile --build=missing --update")
        assert "Updating from git remote" in c.out
        assert "Cloning" in c.out


@pytest.mark.tool("git")
class TestGitRemotesRef:

    def test_branch_ref(self):
        """Profile entry with @branch clones and checks out that branch"""
        repo_url, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("mypkg", "1.0")},
            branch="dev",
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            mypkg/1.0: {repo_url}@dev
            """)
        c.save({
            "profile": profile,
            "conanfile.py": GenConanfile().with_requires("mypkg/1.0"),
        })
        c.run("install . -pr=profile --build=missing")
        assert "mypkg/1.0" in c.out
        assert "git ref: dev" in c.out

    def test_tag_ref(self):
        """Profile entry with @tag clones and checks out that tag"""
        repo_url, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("mypkg", "2.0")},
            tags=["v2.0"],
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            mypkg/2.0: {repo_url}@v2.0
            """)
        c.save({
            "profile": profile,
            "conanfile.py": GenConanfile().with_requires("mypkg/2.0"),
        })
        c.run("install . -pr=profile --build=missing")
        assert "mypkg/2.0" in c.out
        assert "git ref: v2.0" in c.out

    def test_commit_ref(self):
        """Profile entry with @<sha> checks out that exact commit"""
        repo_url, commit = create_local_git_repo(
            files={"conanfile.py": _header_lib("mypkg", "3.0")},
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            mypkg/3.0: {repo_url}@{commit}
            """)
        c.save({
            "profile": profile,
            "conanfile.py": GenConanfile().with_requires("mypkg/3.0"),
        })
        c.run("install . -pr=profile --build=missing")
        assert "mypkg/3.0" in c.out
        assert f"git ref: {commit}" in c.out


@pytest.mark.tool("git")
class TestGitRemotesVersionRange:

    def test_version_range_resolved_via_git_remotes(self):
        """Version range resolves to a version defined in [git_remotes]"""
        repo_url, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("zlib", "1.3.0")}
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            zlib/1.3.0: {repo_url}
            """)
        c.save({
            "profile": profile,
            "conanfile.py": GenConanfile().with_requires("zlib/[>=1.0 <2.0]"),
        })
        c.run("install . -pr=profile --build=missing")
        assert "zlib/1.3.0" in c.out
        assert "resolving from git remote" in c.out

    def test_no_match_falls_through(self):
        """Non-matching package is not handled by git_remotes"""
        repo_url, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("pkga", "1.0")}
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            pkga/1.0: {repo_url}
            """)
        c.save({
            "profile": profile,
            "conanfile.py": GenConanfile().with_requires("pkgb/1.0"),
        })
        c.run("install . -pr=profile --build=missing", assert_error=True)
        assert "pkgb/1.0" in c.out
        # pkga git_remote must not have been invoked
        assert "Resolving from git remote" not in c.out


@pytest.mark.tool("git")
class TestGitRemotesProfileComposition:

    def test_profile_composition_last_wins(self):
        """When two profiles define the same key, the last profile's URL wins"""
        repo_url1, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("zlib", "1.2.11")}
        )
        repo_url2, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("zlib", "1.2.11")}
        )
        c = TestClient(light=True)
        profile1 = textwrap.dedent(f"""\
            [git_remotes]
            zlib/1.2.11: {repo_url1}
            """)
        profile2 = textwrap.dedent(f"""\
            [git_remotes]
            zlib/1.2.11: {repo_url2}
            """)
        c.save({
            "profile1": profile1,
            "profile2": profile2,
            "conanfile.py": GenConanfile().with_requires("zlib/1.2.11"),
        })
        c.run("install . -pr=profile1 -pr=profile2 --build=missing")
        assert "zlib/1.2.11" in c.out
        assert repo_url2 in c.out

    def test_profile_composition_additive(self):
        """Two profiles with different keys: both entries are available"""
        repo_url_a, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("pkga", "1.0")}
        )
        repo_url_b, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("pkgb", "2.0")}
        )
        c = TestClient(light=True)
        profile1 = textwrap.dedent(f"""\
            [git_remotes]
            pkga/1.0: {repo_url_a}
            """)
        profile2 = textwrap.dedent(f"""\
            [git_remotes]
            pkgb/2.0: {repo_url_b}
            """)
        conanfile = textwrap.dedent("""\
            from conan import ConanFile
            class Consumer(ConanFile):
                requires = "pkga/1.0", "pkgb/2.0"
            """)
        c.save({
            "profile1": profile1,
            "profile2": profile2,
            "conanfile.py": conanfile,
        })
        c.run("install . -pr=profile1 -pr=profile2 --build=missing")
        assert "pkga/1.0" in c.out
        assert "pkgb/2.0" in c.out


@pytest.mark.tool("git")
class TestGitRemotesErrors:

    def test_missing_conanfile_in_repo(self):
        """Repo without conanfile.py gives a clear error message"""
        repo_url, _ = create_local_git_repo(
            files={"README.md": "# hello"}
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            zlib/1.2.11: {repo_url}
            """)
        c.save({
            "profile": profile,
            "conanfile.py": GenConanfile().with_requires("zlib/1.2.11"),
        })
        c.run("install . -pr=profile --build=missing", assert_error=True)
        assert "conanfile.py not found" in c.out


@pytest.mark.tool("git")
class TestGitRemotesProfileShow:

    def test_profile_show_displays_git_remotes_section(self):
        """conan profile show includes the [git_remotes] section"""
        c = TestClient(light=True)
        profile = textwrap.dedent("""\
            [git_remotes]
            zlib/1.2.11: https://github.com/example/zlib.git@main
            """)
        c.save({"myprofile": profile})
        c.run("profile show -pr=myprofile")
        assert "[git_remotes]" in c.out
        assert "zlib/1.2.11: https://github.com/example/zlib.git@main" in c.out


@pytest.mark.tool("git")
class TestGitRemotesTransitive:

    def test_transitive_deps_both_from_git_remotes(self):
        """Pkg A from git_remotes requires pkg B, which also has a git_remotes entry"""
        repo_b_url, _ = create_local_git_repo(
            files={"conanfile.py": _header_lib("pkgb", "1.0")}
        )
        conanfile_a = textwrap.dedent("""\
            from conan import ConanFile
            class PkgA(ConanFile):
                name = "pkga"
                version = "1.0"
                package_type = "header-library"
                requires = "pkgb/1.0"
            """)
        repo_a_url, _ = create_local_git_repo(
            files={"conanfile.py": conanfile_a}
        )
        c = TestClient(light=True)
        profile = textwrap.dedent(f"""\
            [git_remotes]
            pkga/1.0: {repo_a_url}
            pkgb/1.0: {repo_b_url}
            """)
        c.save({
            "profile": profile,
            "conanfile.py": GenConanfile().with_requires("pkga/1.0"),
        })
        c.run("install . -pr=profile --build=missing")
        assert "pkga/1.0" in c.out
        assert "pkgb/1.0" in c.out
        assert c.out.count("resolving from git remote") == 2
