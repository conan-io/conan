import json
import os
import re
import subprocess
from unittest import mock

import pytest

from conan.internal.util.files import save
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.scm import create_local_git_repo, git_add_changes_commit
from conan.test.utils.tools import TestClient


@pytest.fixture
def git_repos():
    """Patches GitRemotesResolver._get_url to serve local repos by 'org/repo' slug.
    Yields a register(slug, files, **kwargs) helper that creates a local git repo
    and maps the slug -> local path for the duration of the test."""
    mapping = {}

    def register(slug, files=None, **kwargs):
        path, commit = create_local_git_repo(files, **kwargs)
        mapping[slug] = path
        return path, commit

    with mock.patch(
        "conan.internal.graph.git_remotes_resolver.GitRemotesResolver._get_url",
        side_effect=lambda repo: mapping[repo],
    ):
        yield register


@pytest.mark.tool("git")
class TestGitRemotesBasic:
    """First-run resolution, cache reuse, --update behavior, and support across
    self.requires / self.tool_requires / self.test_requires."""

    def test_basic_resolution_from_git(self, git_repos):
        git_repos("conan-io/zlib", {"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11",
                                                                git="conan-io/zlib")})
        c.run("install . --build=missing")
        assert "resolving from git remote" in c.out
        assert "zlib/1.2.11" in c.out

    def test_cache_first_no_reclone_on_second_run(self, git_repos):
        git_repos("conan-io/zlib", {"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11",
                                                                git="conan-io/zlib")})
        c.run("install . --build=missing")
        assert "resolving from git remote" in c.out

        c.run("install . --build=missing")
        assert "Found in cache (configured via git remote" in c.out
        assert "Cloning" not in c.out

    def test_update_flag_forces_reclone(self, git_repos):
        git_repos("conan-io/zlib", {"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11",
                                                                git="conan-io/zlib")})
        c.run("install . --build=missing")
        c.run("install . --build=missing --update")
        assert "Updating from git remote" in c.out
        assert "Cloning" in c.out

    @pytest.mark.parametrize("method", [
        "with_requirement",       # self.requires(git=)      — host dependency
        "with_tool_requirement",  # self.tool_requires(git=) — build-context tool
        "with_test_requirement",  # self.test_requires(git=) — test-only host dependency
    ])
    def test_resolution_by_require_type(self, method, git_repos):
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "1.0")})
        consumer = getattr(GenConanfile(), method)("mypkg/1.0", git="myorg/mypkg")
        c = TestClient(light=True)
        c.save({"conanfile.py": str(consumer)})
        c.run("install . --build=missing")
        assert "resolving from git remote" in c.out
        assert "mypkg/1.0" in c.out


@pytest.mark.tool("git")
class TestGitRemotesRef:
    """The ``git="org/repo[@ref]"`` mini-DSL: branch/tag/commit refs, parsing
    corner cases, and refs containing shell-special or ambiguous characters."""

    def test_branch_ref(self, git_repos):
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "1.0")}, branch="dev")
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg@dev")})
        c.run("install . --build=missing")
        assert "mypkg/1.0" in c.out
        assert "git ref: dev" in c.out

    def test_tag_ref(self, git_repos):
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "2.0")}, tags=["v2.0"])
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/2.0",
                                                                git="myorg/mypkg@v2.0")})
        c.run("install . --build=missing")
        assert "mypkg/2.0" in c.out
        assert "git ref: v2.0" in c.out

    def test_commit_ref(self, git_repos):
        _, commit = git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "3.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/3.0",
                                                                git=f"myorg/mypkg@{commit}")})
        c.run("install . --build=missing")
        assert "mypkg/3.0" in c.out
        assert f"git ref: {commit}" in c.out

    def test_at_in_ref_name_resolves(self, git_repos):
        """Refs may contain '@' (git allows it; only '@{' is forbidden). We split
        on the FIRST '@' — GitHub org/repo names can't contain '@' — so anything
        after is the ref, even if the ref itself has further '@'s.
        """
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "1.0")},
                  branch="foo@bar")
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg@foo@bar")})
        c.run("install . --build=missing")
        assert "git ref: foo@bar" in c.out
        assert "mypkg/1.0" in c.out

    def test_ref_with_shell_metacharacter_resolves(self, git_repos):
        """Refs with shell metacharacters (like '&') are legal in git but would
        break if the resolver interpolated the ref into a shell string. The
        resolver must invoke git via argv, not shell=True."""
        repo_path, _ = git_repos("myorg/mypkg",
                                 {"conanfile.py": GenConanfile("mypkg", "1.0")})
        tag = "v1&hotfix"
        subprocess.run(["git", "-C", repo_path, "tag", tag], check=True, capture_output=True)

        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git=f"myorg/mypkg@{tag}")})
        c.run("install . --build=missing")
        assert f"git ref: {tag}" in c.out
        assert "mypkg/1.0" in c.out

    def test_trailing_at_is_error(self, git_repos):
        """A trailing '@' with an empty ref is almost always a typo. Reject it
        rather than silently falling back to the default branch."""
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "1.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0", git="myorg/mypkg@")})
        c.run("install . --build=missing", assert_error=True)
        assert "trailing '@'" in c.out
        assert "myorg/mypkg@" in c.out
        assert "Cloning git repository" not in c.out

    def test_revision_and_git_ref_together_error(self):
        """A require may pin a commit either by recipe revision ('pkg/1.0#<sha>')
        OR by ref in git= ('org/repo@<sha>') — not both. Under revision_mode='scm'
        those two pins refer to the same identity, so specifying both from the
        recipe is ambiguous. Missing conflict is reported clearly."""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement(
            "zlib/1.2.11#" + "a" * 32, git="conan-io/zlib@main")})
        c.run("install . --build=missing", assert_error=True)
        assert "zlib/1.2.11" in c.out
        assert "use only one" in c.out


@pytest.mark.tool("git")
class TestGitRemotesContract:
    """The require declares (name, version) and git= points at a source repo;
    these tests pin how the two are reconciled.

    Contract:
      - If the recipe hardcodes name/version, they MUST match the require
        (enforced by cmd_export -> load_named). Mismatch → hard error.
      - If the recipe does NOT declare name/version, the require's values are
        used verbatim. git= is 'trust the URL' — the repo can host arbitrary
        content and be labeled with any (name, version) the consumer picks.
      - Version ranges: clone first; the recipe's declared version is validated
        against the range and, if it passes, becomes the resolved version.
        Out-of-range → hard error.
    """

    def test_missing_conanfile_in_repo(self, git_repos):
        git_repos("myorg/myrepo", {"README.md": "# hello"})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11",
                                                                git="myorg/myrepo")})
        c.run("install . --build=missing", assert_error=True)
        assert "conanfile.py not found" in c.out

    def test_repo_hardcodes_different_name_errors(self, git_repos):
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("wrongname", "1.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg")})
        c.run("install . --build=missing", assert_error=True)
        assert "Package recipe with name mypkg!=wrongname" in c.out

    def test_repo_hardcodes_different_version_errors(self, git_repos):
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "9.9.9")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg")})
        c.run("install . --build=missing", assert_error=True)
        assert "Package recipe with version 1.0!=9.9.9" in c.out

    def test_repo_declares_nothing_git_is_authoritative(self, git_repos):
        """No name/version declared by the recipe → the require's values win."""
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile()})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg")})
        c.run("install . --build=missing")
        assert "mypkg/1.0" in c.out

    def test_version_range_resolves_from_repo(self, git_repos):
        """Version range + git=: the recipe's declared version is checked
        against the range and, if it fits, becomes the resolved version."""
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/[>=1.0]",
                                                                git="myorg/mypkg")})
        c.run("install . --build=missing")
        assert "resolved version: 1.2.11" in c.out
        assert "mypkg/1.2.11" in c.out

    def test_version_range_out_of_range_errors(self, git_repos):
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "0.5")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/[>=1.0]",
                                                                git="myorg/mypkg")})
        c.run("install . --build=missing", assert_error=True)
        assert "does not accept the version '0.5'" in c.out


@pytest.mark.tool("git")
class TestGitRemotesTransitive:
    """Chains and diamonds where multiple nodes use git= to source their recipes."""

    def test_transitive_deps_both_from_git(self, git_repos):
        git_repos("myorg/pkgb", {"conanfile.py": GenConanfile("pkgb", "1.0")})
        git_repos("myorg/pkga",
                  {"conanfile.py": GenConanfile("pkga", "1.0")
                   .with_requirement("pkgb/1.0", git="myorg/pkgb")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("pkga/1.0", git="myorg/pkga")})
        c.run("install . --build=missing")
        assert "pkga/1.0" in c.out
        assert "pkgb/1.0" in c.out
        assert c.out.count("resolving from git remote") == 2

    def test_diamond_all_from_git(self, git_repos):
        """Diamond: consumer->pkga->pkgc and consumer->pkgb->pkgc, all from git.
        pkgc is cloned once; the second encounter finds it in cache."""
        git_repos("myorg/pkgc", {"conanfile.py": GenConanfile("pkgc", "1.0")})
        git_repos("myorg/pkga",
                  {"conanfile.py": GenConanfile("pkga", "1.0")
                   .with_requirement("pkgc/1.0", git="myorg/pkgc")})
        git_repos("myorg/pkgb",
                  {"conanfile.py": GenConanfile("pkgb", "1.0")
                   .with_requirement("pkgc/1.0", git="myorg/pkgc")})
        c = TestClient(light=True)
        c.save({"conanfile.py": str(
            GenConanfile()
            .with_requirement("pkga/1.0", git="myorg/pkga")
            .with_requirement("pkgb/1.0", git="myorg/pkgb"))})
        c.run("install . --build=missing")
        assert "pkga/1.0" in c.out
        assert "pkgb/1.0" in c.out
        assert "pkgc/1.0" in c.out
        assert c.out.count("resolving from git remote") == 3
        assert c.out.count("Found in cache (configured via git remote") == 1


@pytest.mark.tool("git")
class TestGitRemotesLockfile:
    """Lockfile capture/reuse. Under revision_mode='scm' the recipe revision IS
    the git commit SHA, which makes lockfiles reproducible across branch drift."""

    def test_lockfile_happy_path(self, git_repos):
        git_repos("conan-io/zlib", {"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11",
                                                                git="conan-io/zlib")})

        # First install: clone from git, export to cache, write lockfile
        c.run("install . --build=missing --lockfile-out=conan.lock")
        assert "resolving from git remote" in c.out
        assert "zlib/1.2.11" in c.out

        # Lockfile carries zlib/1.2.11 with a recipe revision
        lock = json.loads(c.load("conan.lock"))
        (locked_ref,) = lock["requires"]
        assert locked_ref.startswith("zlib/1.2.11#")
        assert locked_ref.split("#")[1]

        # Second install with lockfile: recipe already in cache → no clone
        c.run("install . --lockfile=conan.lock")
        assert "Found in cache (configured via git remote" in c.out
        assert "Cloning" not in c.out
        assert "zlib/1.2.11" in c.out

        # Cache purged: lockfile drives a checkout of the locked commit (fresh
        # clone, folder keyed by the locked SHA). Install still succeeds.
        c.run("remove * -c")
        c.run("install . --lockfile=conan.lock --build=missing")
        assert "zlib/1.2.11" in c.out

    def test_recipe_revision_is_git_commit(self, git_repos):
        """The revision annotated on the require (and stored in the lockfile)
        equals the HEAD commit SHA of the cloned repo."""
        _, expected_sha = git_repos("myorg/mypkg",
                                    {"conanfile.py": GenConanfile("mypkg", "1.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg")})
        c.run("install . --build=missing --lockfile-out=conan.lock")

        lock = json.loads(c.load("conan.lock"))
        (locked_ref,) = lock["requires"]
        # Lockfile encodes 'ref#revision%timestamp'; keep only the revision
        m = re.fullmatch(r"mypkg/1\.0#([0-9a-f]+)(?:%.*)?", locked_ref)
        assert m and m.group(1) == expected_sha, (locked_ref, expected_sha)

    def test_lockfile_reproduces_after_branch_advances(self, git_repos):
        """Capture a lockfile pointing to a branch; advance the branch upstream;
        reinstall from the lockfile on a cold cache — the OLD commit is checked
        out because the lockfile pins the SHA."""
        repo_path, first_sha = git_repos("myorg/mypkg",
                                         {"conanfile.py": GenConanfile("mypkg", "1.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg")})
        c.run("install . --build=missing --lockfile-out=conan.lock")

        save(os.path.join(repo_path, "conanfile.py"),
             str(GenConanfile("mypkg", "1.0").with_class_attribute("marker='v2'")))
        second_sha = git_add_changes_commit(repo_path)
        assert second_sha != first_sha

        c.run("remove * -c")
        c.run("cache clean --temp")

        c.run("install . --lockfile=conan.lock --build=missing")
        assert f"mypkg/1.0#{first_sha}" in c.out

    def test_lockfile_revision_mismatch_fails(self, git_repos):
        """Tampered lockfile (revision replaced with a bogus one) is caught by
        the graph_lock check: the exported/cached revision does not match the
        locked revision → clear error."""
        repo_path, _ = git_repos("conan-io/zlib",
                                 {"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11",
                                                                git="conan-io/zlib")})

        c.run("install . --build=missing --lockfile-out=conan.lock")
        assert "resolving from git remote" in c.out

        raw = c.load("conan.lock")
        tampered = re.sub(r"(zlib/1\.2\.11#)[0-9a-f]+", r"\1deadbeef00000000000000000000000", raw)
        c.save({"conan2.lock": tampered})

        c.run("install . --lockfile=conan2.lock", assert_error=True)
        assert "zlib/1.2.11" in c.out
        assert re.search(r"Requirement 'zlib/1\.2\.11#[0-9a-f]+' not in lockfile 'requires'",
                         c.out)

        # Cache purged: lockfile still drives checkout of the locked commit
        c.run("remove * -c")
        c.run("install . --lockfile=conan.lock --build=missing")
        assert "zlib/1.2.11" in c.out

        # Branch advances upstream. Lockfile still pins the old SHA, so the
        # reinstall reproduces the old commit — no revision mismatch.
        save(os.path.join(repo_path, "conanfile.py"),
             str(GenConanfile("zlib", "1.2.11").with_class_attribute("somevar=3")))
        git_add_changes_commit(repo_path)
        c.run("remove * -c")
        c.run("install . --lockfile=conan.lock --build=missing")
        assert "zlib/1.2.11" in c.out


@pytest.mark.tool("git")
class TestGitRemotesPrecedence:
    """git= is a source hint, not an override. Other mechanisms that redirect
    or override a requirement (profile [replace_requires], editable packages)
    take precedence — the git prefetch is skipped, with visible feedback."""

    def test_replace_requires_wins_over_git(self, git_repos):
        git_repos("myorg/zlib", {"conanfile.py": GenConanfile("zlib", "1.2.11")})
        c = TestClient(light=True)
        c.save({"replacement/conanfile.py": GenConanfile("my_zlib", "1.0")})
        c.run("export replacement")

        profile = "[replace_requires]\nzlib/*: my_zlib/1.0"
        c.save({"conanfile.py": GenConanfile().with_requirement("zlib/1.2.11", git="myorg/zlib"),
                "myprofile": profile})
        c.run("install . -pr=myprofile --build=missing")
        assert "Ignoring git=" in c.out
        assert "my_zlib/1.0" in c.out
        assert "Cloning git repository" not in c.out

    def test_revision_on_require_pins_git_checkout(self, git_repos):
        """A require of the form ``pkg/version#<sha>`` combined with a
        commit-less ``git="org/repo"`` — under revision_mode='scm' the recipe
        revision IS the git SHA, so the two annotations refer to the same
        identity and could reasonably drive a git checkout of that commit.
        NOT supported today: prefetch rejects revision + git= as inconsistent.
        Companion to test_revision_with_git_is_error (which pins the current
        rejection behavior).
        """
        repo_path, first_sha = git_repos("myorg/mypkg",
                                         {"conanfile.py": GenConanfile("mypkg", "1.0")})
        # Branch advances upstream — the require should still resolve to first_sha
        save(os.path.join(repo_path, "conanfile.py"),
             str(GenConanfile("mypkg", "1.0").with_class_attribute("marker='v2'")))
        second_sha = git_add_changes_commit(repo_path)
        assert second_sha != first_sha

        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement(
            f"mypkg/1.0#{first_sha}", git="myorg/mypkg")})
        c.run("install . --build=missing")

        assert f"mypkg/1.0#{first_sha}" in c.out
        assert second_sha not in c.out

    def test_replace_requires_pins_commit_over_recipe_branch(self, git_repos):
        """Same reproducibility pattern as test_replace_requires_pins_commit_from_profile,
        but the recipe already carries a branch ref: ``git="myorg/mypkg@main"``.
        The profile [replace_requires] adds a specific revision on top. Intent:
        the profile-supplied commit should override the recipe's branch pin —
        replace_requires is an explicit, out-of-recipe knob and its revision
        should take precedence.

        Currently FAILS: with both @ref (from git=) and #revision (from
        replace_requires) present, prefetch raises "use only one".
        """
        repo_path, first_sha = git_repos("myorg/mypkg",
                                         {"conanfile.py": GenConanfile("mypkg", "1.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement(
            "mypkg/1.0", git="myorg/mypkg@main")})

        # Branch advances upstream
        save(os.path.join(repo_path, "conanfile.py"),
             str(GenConanfile("mypkg", "1.0").with_class_attribute("marker='v2'")))
        second_sha = git_add_changes_commit(repo_path)
        assert second_sha != first_sha

        profile = f"[replace_requires]\nmypkg/1.0: mypkg/1.0#{first_sha}"
        c.save({"myprofile": profile})
        c.run("install . -pr=myprofile --build=missing")

        assert f"mypkg/1.0#{first_sha}" in c.out
        assert second_sha not in c.out

    def test_replace_requires_pins_commit_from_profile(self, git_repos):
        """A user tries to pin a specific commit via profile [replace_requires]
        (name/version unchanged, revision added), so builds reproduce even after
        the branch tip has moved — analogous to the lockfile-driven flow but
        on-demand from a profile. Currently NOT supported: [replace_requires]
        takes precedence and skips the git prefetch entirely, so the resolver
        looks for the pinned revision in the cache (miss) rather than driving
        a git checkout of that commit.
        """
        repo_path, first_sha = git_repos("myorg/mypkg",
                                         {"conanfile.py": GenConanfile("mypkg", "1.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg")})

        # Branch advances upstream after we recorded 'first_sha'
        save(os.path.join(repo_path, "conanfile.py"),
             str(GenConanfile("mypkg", "1.0").with_class_attribute("marker='v2'")))
        second_sha = git_add_changes_commit(repo_path)
        assert second_sha != first_sha

        # Profile pins the earlier commit as the revision to install
        profile = f"[replace_requires]\nmypkg/1.0: mypkg/1.0#{first_sha}"
        c.save({"myprofile": profile})
        c.run("install . -pr=myprofile --build=missing")

        # Reproducibility win: first commit is checked out, not the new tip
        assert f"mypkg/1.0#{first_sha}" in c.out
        assert second_sha not in c.out

    def test_editable_wins_over_git(self, git_repos):
        """An editable registration for the same ref short-circuits git=.
        The git URL is intentionally bad (no conanfile.py) so a stray clone
        would blow up — proving the editable path took over."""
        git_repos("myorg/mypkg", {"README.md": "not a conanfile"})
        c = TestClient(light=True)
        c.save({"editable/conanfile.py": GenConanfile("mypkg", "1.0")})
        c.run("editable add editable")

        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg")})
        c.run("install . --build=missing")
        assert "mypkg/1.0" in c.out
        assert "Cloning git repository" not in c.out
        assert "conanfile.py not found" not in c.out


@pytest.mark.tool("git")
class TestGitRemotesLifecycle:
    """Lifecycle of the on-disk git_clones/ folder: cleanup on demand, and
    auto-recovery from a half-clone left by a previous interrupted run."""

    def test_cache_clean_removes_git_clones(self, git_repos):
        git_repos("myorg/mypkg", {"conanfile.py": GenConanfile("mypkg", "1.0")})
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0", git="myorg/mypkg")})
        c.run("install . --build=missing")

        clones_root = c.cache.git_clones_folder
        assert os.path.isdir(clones_root) and os.listdir(clones_root)

        c.run("cache clean --temp")
        assert not os.path.exists(clones_root) or not os.listdir(clones_root)

    def test_dirty_clone_auto_recovers_on_next_run(self, git_repos):
        """Interrupted clone/checkout leaves a .dirty marker; the next run
        against the same ref detects it, re-clones from scratch, and succeeds
        without --update or manual cleanup."""
        repo_path, _ = git_repos("myorg/mypkg",
                                 {"conanfile.py": GenConanfile("mypkg", "1.0")})
        c = TestClient(light=True)

        # First attempt: tag doesn't exist yet → checkout fails → dirty stays
        c.save({"conanfile.py": GenConanfile().with_requirement("mypkg/1.0",
                                                                git="myorg/mypkg@v1.0")})
        c.run("install . --build=missing", assert_error=True)

        clones_root = c.cache.git_clones_folder
        subdirs = os.listdir(clones_root)
        assert any(name.endswith(".dirty") for name in subdirs)

        # Upstream fixed: the tag now exists in the remote
        subprocess.run(["git", "-C", repo_path, "tag", "v1.0"],
                       check=True, capture_output=True)

        c.run("install . --build=missing")
        assert "mypkg/1.0" in c.out
        subdirs = os.listdir(clones_root)
        assert not any(name.endswith(".dirty") for name in subdirs), subdirs
