import hashlib
import os

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.api.export import cmd_export
from conan.internal.util.files import rmdir
from conan.internal.util.runners import detect_runner


class GitRemotesResolver:

    def __init__(self, cache, global_conf):
        self._cache = cache
        self._global_conf = global_conf
        self._clones_base = os.path.join(cache.store, "git_clones")

    def clone_and_export(self, ref, git_spec, loader, hook_manager, force_clone=False):
        clone_folder = self._clone_folder(git_spec)
        if force_clone and os.path.exists(clone_folder):
            rmdir(clone_folder)
        if not os.path.exists(clone_folder):
            self._do_clone(git_spec, clone_folder)
        conanfile_path = os.path.join(clone_folder, "conanfile.py")
        if not os.path.exists(conanfile_path):
            raise ConanException(
                f"conanfile.py not found at root of git repo '{git_spec.url}'")
        return cmd_export(loader, self._cache, hook_manager, self._global_conf,
                          conanfile_path, ref.name, str(ref.version),
                          ref.user, ref.channel, graph_lock=None, remotes=None)

    def _clone_folder(self, git_spec):
        key = f"{git_spec.url}:{git_spec.ref or ''}"
        h = hashlib.md5(key.encode()).hexdigest()[:12]
        return os.path.join(self._clones_base, h)

    @staticmethod
    def _do_clone(git_spec, clone_folder):
        output = ConanOutput()
        os.makedirs(clone_folder, exist_ok=True)
        output.info(f"Cloning git repository '{git_spec.url}'...")
        ret, out = detect_runner(f'git clone "{git_spec.url}" "{clone_folder}"')
        if ret != 0:
            rmdir(clone_folder)
            raise ConanException(f"git clone failed for '{git_spec.url}':\n{out}")
        if git_spec.ref:
            output.info(f"Checking out git ref '{git_spec.ref}'...")
            ret, out = detect_runner(
                f'git -C "{clone_folder}" checkout {git_spec.ref}')
            if ret != 0:
                raise ConanException(
                    f"git checkout '{git_spec.ref}' failed for '{git_spec.url}':\n{out}")
