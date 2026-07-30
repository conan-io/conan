import hashlib
import os
import subprocess

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.api.export import cmd_export
from conan.internal.graph.proxy import should_update_reference
from conan.internal.util.files import remove_if_dirty, rmdir, set_dirty_context_manager


class GitRemotesResolver:

    def __init__(self, cache):
        self._cache = cache
        self._clones_base = cache.git_clones_folder

    @staticmethod
    def _get_url(repo):
        # Maybe we need to extend this to gitlab too, we could check a "gl:org/repo" format
        return f"https://github.com/{repo}.git"

    def prefetch(self, node, require, update, loader, editable_packages, lockfile=None):
        """If the requirement declares a git= source, clone and export it into the local
        cache before range resolution and proxy lookup run. Mirrors the
        _resolve_replace_requires pattern — invoked early in _initialize_requires so the
        rest of graph resolution is transparent (proxy just finds the recipe in cache).

        Semantics:
          - The recipe revision IS the git commit SHA (revision_mode='scm' is forced
            during export). A lockfile captured today pins the exact commit, so a
            later reinstall from that lockfile can reproduce the build even if a
            branch tip has moved in the meantime.
          - Version ranges are allowed. The clone runs first, the recipe declares its
            own version, and the resolver validates that the declared version is
            within the require's range.
        """
        ref = require.ref
        # replace_requires ran and matched: _resolve_replace_requires sets
        # _required_ref = ref.copy() BEFORE mutating ref. If they are no longer the same
        # object, the ref was renamed and the hardcoded git= source cannot apply —
        # replace_requires wins.
        output = ConanOutput(scope=str(node))
        if require._required_ref is not ref:  # noqa
            output.warning(f"Ignoring git={require.git!r}: 'replace_requires' matched "
                           f"and took precedence over the git= source.")
            return

        # Editable takes precedence over git=: a local editable is a stronger
        # override than a hardcoded remote source.
        if editable_packages is not None and editable_packages.get(ref) is not None:
            output.info(f"Ignoring git={require.git!r}: package is in editable mode.")
            return

        if ref.revision:
            raise ConanException(
                f"Requirement '{ref}' with an explicit revision cannot use a 'git=' source")

        git = require.git  # raw string: "org/repo" or "org/repo@ref"
        # split on the FIRST '@' — org/repo cannot contain '@' (GitHub disallows it),
        # so anything after is the ref, even if the ref itself contains '@'
        idx = git.split("@", 1)
        if len(idx) == 2 and not idx[1]:
            raise ConanException(
                f"Requirement '{ref}': git={git!r} has a trailing '@' with no ref. "
                f"Drop the '@' to use the default branch, or specify a branch/tag/commit.")
        repo, git_ref = idx if len(idx) == 2 else (idx[0], None)

        # Lockfile-driven checkout: if a matching entry is locked with a revision
        # (git commit SHA under our revision_mode='scm' contract), use it as the
        # checkout target so reinstalls reproduce the exact commit even if the
        # branch has moved upstream. Peek only — do NOT let resolve_locked mutate
        # require.ref to share identity with the lockfile's internal ref (that
        # would cause our later revision assignment to poison the lockfile).
        if lockfile is not None:
            saved_ref = require.ref
            try:
                lockfile.resolve_locked(node, require, resolve_prereleases=None)
                locked_rev = require.ref.revision
            except ConanException:
                locked_rev = None
            finally:
                require.ref = saved_ref
            if locked_rev:
                git_ref = locked_rev

        url = self._get_url(repo)
        force_clone = should_update_reference(ref, update)
        version_range = require.version_range

        output = ConanOutput(scope=str(ref))
        if force_clone:
            output.info(f"Updating from git remote '{url}'...")
        elif not version_range:
            # Cache-first shortcut only makes sense for a fully-resolved ref.
            # With a range, we need to re-resolve which concrete version applies.
            try:
                layout = self._cache.recipe_layout_latest(ref)
                require.ref.revision = layout.reference.revision
                output.info(f"Found in cache (configured via git remote '{url}')")
                return
            except ConanException:
                pass  # Not in cache — proceed with clone+export
            output.info(f"Not found in local cache, resolving from git remote '{url}'")

        if git_ref:
            output.info(f"  git ref: {git_ref}")

        # With a version range, let the recipe declare its own version and validate
        # it after export. Without a range, pass the exact version so cmd_export
        # enforces the recipe hardcodes match (existing behavior).
        version = None if version_range else str(ref.version)
        exported_ref, _ = self._clone_and_export(ref, repo, git_ref, loader,
                                                 force_clone, version=version)

        if version_range:
            resolved_version = exported_ref.version
            resolve_prereleases = None  # let VersionRange default apply
            if not version_range.contains(resolved_version, resolve_prereleases):
                raise ConanException(
                    f"Requirement '{ref}' with range '{version_range}' does not accept "
                    f"the version '{resolved_version}' declared by the recipe at "
                    f"git remote '{url}'")
            output.info(f"  resolved version: {resolved_version} (in range {version_range})")
            require.ref.version = resolved_version

        # Recipe revision is the git commit SHA (revision_mode='scm' forced during export)
        require.ref.revision = exported_ref.revision

    def _clone_and_export(self, ref, repo, git_ref, loader, force_clone, version=None):
        url = self._get_url(repo)
        clone_folder = self._clone_folder(url, git_ref)
        # Leftover from a previous run interrupted mid-clone/checkout: discard it
        remove_if_dirty(clone_folder)
        if force_clone and os.path.exists(clone_folder):
            rmdir(clone_folder)
        if not os.path.exists(clone_folder):
            self._do_clone(url, git_ref, clone_folder)
        conanfile_path = os.path.join(clone_folder, "conanfile.py")
        if not os.path.exists(conanfile_path):
            raise ConanException(
                f"conanfile.py not found at root of git repo '{url}'")

        # Hooks are intentionally skipped: git= is aimed at open-source /
        # community workflows that pull recipes straight from public github.com
        # repos, not at organizations that rely on pre/post_export hooks for
        # policy, signing or scanning.
        class _NoopHooks:
            def execute(self, *a, **kw): pass

        from conan.internal.model.conf import ConfDefinition
        # Force revision_mode='scm' → recipe revision = git commit SHA. Enables
        # lockfile reproducibility even against moving branches.
        # no remotes, no lockfile, as python-requires are not supported now
        return cmd_export(loader, self._cache, _NoopHooks(), ConfDefinition(),
                          conanfile_path, ref.name, version,
                          ref.user, ref.channel, revision_mode_scm=True)

    def _clone_folder(self, url, git_ref):
        key = f"{url}:{git_ref or ''}"
        h = hashlib.md5(key.encode()).hexdigest()[:12]
        return os.path.join(self._clones_base, h)

    @staticmethod
    def _run_git(argv):
        # argv-form; never shell=True — keeps refs/URLs with metachars intact
        proc = subprocess.run(argv, capture_output=True, text=True)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    @classmethod
    def _do_clone(cls, url, git_ref, clone_folder):
        output = ConanOutput()
        os.makedirs(clone_folder, exist_ok=True)
        # dirty marker: if the process is interrupted mid-clone/checkout, the
        # next run detects the marker via remove_if_dirty and starts fresh
        with set_dirty_context_manager(clone_folder):
            output.info(f"Cloning git repository '{url}'...")
            ret, out = cls._run_git(["git", "clone", url, clone_folder])
            if ret != 0:
                raise ConanException(f"git clone failed for '{url}':\n{out}")
            if git_ref:
                output.info(f"Checking out git ref '{git_ref}'...")
                ret, out = cls._run_git(["git", "-C", clone_folder, "checkout", git_ref])
                if ret != 0:
                    raise ConanException(
                        f"git checkout '{git_ref}' failed for '{url}':\n{out}")
