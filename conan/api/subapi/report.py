import base64
import os

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.api.model import RecipeReference
from conan.internal.conan_app import ConanApp
from conan.internal.errors import conanfile_exception_formatter
from conan.internal.graph.graph import CONTEXT_HOST
from conan.internal.graph.profile_node_definer import initialize_conanfile_profile
from conan.internal.source import config_source


class ReportAPI:
    def __init__(self, conan_api):
        self.conan_api = conan_api

    def diff(self, old_reference, new_reference, remotes, old_path=None, new_path=None, cwd=None):
        """
        Compare two recipes and return the differences.
        :param old_reference: The reference of the old recipe.
        :param new_reference: The reference of the new recipe.
        :param remotes: List of remotes to search for the recipes.
        :param old_path: Optional path to the old recipe's conanfile.py.
        :param new_path: Optional path to the new recipe's conanfile.py.
        :param cwd: Current working directory, used to resolve paths.
        :return: A dictionary with the differences between the two recipes.
        """

        def _source(path_to_conanfile, reference):
            if path_to_conanfile is None:
                export_ref, cache_path = _download_ref_from_remote(self.conan_api, reference, remotes)
            else:
                export_ref, cache_path = _export_recipe_from_path(self.conan_api, path_to_conanfile,
                                                                  reference, remotes, cwd)
            exported_path = self.conan_api.local.get_conanfile_path(cache_path, cwd, py=True)
            _configure_source(self.conan_api, exported_path, export_ref, remotes)
            return export_ref, cache_path


        old_export_ref, old_cache_path = _source(old_path, old_reference)
        new_export_ref, new_cache_path = _source(new_path, new_reference)

        old_diff_path = os.path.abspath(os.path.join(old_cache_path, os.path.pardir)).replace("\\",
                                                                                              "/")
        new_diff_path = os.path.abspath(os.path.join(new_cache_path, os.path.pardir)).replace("\\",
                                                                                              "/")

        src_prefix = base64.b64encode(str(new_export_ref).encode()).decode() + "/"
        dst_prefix = base64.b64encode(str(old_export_ref).encode()).decode() + "/"

        command = (f'git diff --no-index --src-prefix {src_prefix} --dst-prefix {dst_prefix} '
                   f'"{old_diff_path}" "{new_diff_path}"')

        ConanOutput().info(
            f"Generating diff from {old_export_ref.repr_notime()} to {new_export_ref.repr_notime()} (this might take a while)")
        ConanOutput().info(command)

        # TODO: This is internal, we should use the public API, but nothing exposes functionality like this
        # We ignore the errors because git diff returns 1 if there are differences
        diff = _execute_command(command, ignore_error=True)

        if old_path:
            self.conan_api.remove.recipe(old_export_ref)
        if new_path:
            self.conan_api.remove.recipe(new_export_ref)

        return {
            "diff": diff,
            "old_export_ref": old_export_ref,
            "new_export_ref": new_export_ref,
            "old_diff_path": old_diff_path,
            "new_diff_path": new_diff_path,
            "src_prefix": src_prefix,
            "dst_prefix": dst_prefix,
        }

def _configure_source(conan_api, conanfile_path, ref, remotes):
    app = ConanApp(conan_api)
    conanfile = app.loader.load_consumer(conanfile_path, name=ref.name, version=str(ref.version),
                                         user=ref.user, channel=ref.channel, graph_lock=None,
                                         remotes=remotes)
    # This profile is empty, but with the conf from global.conf
    profile = conan_api.profiles.get_profile([])
    initialize_conanfile_profile(conanfile, profile, profile, CONTEXT_HOST, False)
    # This is important, otherwise the ``conan source`` doesn't define layout and fails
    if hasattr(conanfile, "layout"):
        with conanfile_exception_formatter(conanfile, "layout"):
            conanfile.layout()

    recipe_layout = app.cache.recipe_layout(ref)
    export_source_folder = recipe_layout.export_sources()
    source_folder = recipe_layout.source()

    conanfile.folders.set_base_source(source_folder)
    conanfile.folders.set_base_export_sources(export_source_folder)
    conanfile.folders.set_base_recipe_metadata(recipe_layout.metadata())
    config_source(export_source_folder, conanfile, conan_api.config.hook_manager)

def _execute_command(cmd, stderr=None, ignore_error=False):
    # From internal, but here modified to test encoding issues
    assert isinstance(cmd, str)
    import tempfile
    d = tempfile.mkdtemp()
    tmp_file = os.path.join(d, "output")
    output = None
    try:
        # We don't want stderr to print warnings that will mess the pristine outputs
        import subprocess
        stderr = stderr or subprocess.PIPE
        command = '{} > "{}"'.format(cmd, tmp_file)
        process = subprocess.Popen(command, shell=True, stderr=stderr)
        stdout, stderr = process.communicate()

        if process.returncode and not ignore_error:
            # Only in case of error, we print also the stderr to know what happened
            msg = f"Command '{cmd}' failed with errorcode '{process.returncode}'\n{stderr}"
            raise ConanException(msg)

        with open(tmp_file, 'r', encoding="utf-8", newline="", errors="ignore") as handle:
            output = handle.read()
    finally:
        try:
            os.unlink(tmp_file)
        except OSError:
            pass
        return output


def _download_ref_from_remote(conan_api, reference, enabled_remotes):
    ref = RecipeReference.loads(reference)
    full_ref, matching_remote = None, None
    for remote in enabled_remotes:
        if ref.revision:
            no_rrev_ref = RecipeReference.loads(reference)
            no_rrev_ref.revision = None
            try:
                remote_revisions = conan_api.list.recipe_revisions(no_rrev_ref, remote)
                if ref in remote_revisions:
                    full_ref = ref
                    matching_remote = remote
                    break
            except:
                continue
        else:
            try:
                latest_recipe_revision = conan_api.list.latest_recipe_revision(ref, remote)
            except:
                continue
            if full_ref is None or (latest_recipe_revision.timestamp > full_ref.timestamp):
                full_ref = latest_recipe_revision
                matching_remote = remote
    if full_ref is None or matching_remote is None:
        raise ConanException(f"No matching reference for {reference} in remotes.\n"
                             "If you want to check against a local recipe, add an additional --{old,new}-path arg.\n")

    conan_api.download.recipe(full_ref, matching_remote)
    cache_path = conan_api.cache.export_path(full_ref)
    return full_ref, cache_path


def _export_recipe_from_path(conan_api, path_to_conanfile, reference, enabled_remotes, cwd=None):
    path = conan_api.local.get_conanfile_path(path_to_conanfile, cwd, py=True)
    ref = RecipeReference.loads(reference)
    export_ref, conanfile = conan_api.export.export(path=path,
                                                    name=ref.name, version=str(ref.version),
                                                    user=ref.user, channel=ref.channel,
                                                    lockfile=None,
                                                    remotes=enabled_remotes)
    cache_path = conan_api.cache.export_path(export_ref)
    return export_ref, cache_path
