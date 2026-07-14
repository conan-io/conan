import hashlib
import os

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.api.export import cmd_export
from conan.internal.util.files import rmdir
from conan.internal.util.runners import detect_runner


class GitRemotesResolver:

    def __init__(self, cache):
        self._cache = cache
        self._clones_base = os.path.join(cache.store, "git_clones")

    @staticmethod
    def get_url(repo):
        # Maybe we need to extend this to gitlab too, we could check a "gl:org/repo" format
        return f"https://github.com/{repo}.git"

    def clone_and_export(self, ref, repo, git_ref, loader, force_clone=False):
        url = self.get_url(repo)
        clone_folder = self._clone_folder(url, git_ref)
        if force_clone and os.path.exists(clone_folder):
            rmdir(clone_folder)
        if not os.path.exists(clone_folder):
            self._do_clone(url, git_ref, clone_folder)
        conanfile_path = os.path.join(clone_folder, "conanfile.py")
        if not os.path.exists(conanfile_path):
            raise ConanException(
                f"conanfile.py not found at root of git repo '{url}'")

        class _NoopHooks:
            def execute(self, *a, **kw): pass

        from conan.internal.model.conf import ConfDefinition
        return cmd_export(loader, self._cache, _NoopHooks(), ConfDefinition(),
                          conanfile_path, ref.name, str(ref.version),
                          ref.user, ref.channel, graph_lock=None, remotes=None)

    def _clone_folder(self, url, git_ref):
        key = f"{url}:{git_ref or ''}"
        h = hashlib.md5(key.encode()).hexdigest()[:12]
        return os.path.join(self._clones_base, h)

    @staticmethod
    def _do_clone(url, git_ref, clone_folder):
        output = ConanOutput()
        os.makedirs(clone_folder, exist_ok=True)
        output.info(f"Cloning git repository '{url}'...")
        ret, out = detect_runner(f'git clone "{url}" "{clone_folder}"')
        if ret != 0:
            rmdir(clone_folder)
            raise ConanException(f"git clone failed for '{url}':\n{out}")
        if git_ref:
            output.info(f"Checking out git ref '{git_ref}'...")
            ret, out = detect_runner(f'git -C "{clone_folder}" checkout {git_ref}')
            if ret != 0:
                raise ConanException(
                    f"git checkout '{git_ref}' failed for '{url}':\n{out}")
