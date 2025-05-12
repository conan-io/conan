import os

from conan.api.output import ConanOutput
from conan.cli.formatters.compare.compare import format_compare_html, format_compare_txt, \
    format_compare_json
from conan.errors import ConanException
from conan.api.conan_api import ConanAPI
from conan.cli.command import conan_command
from conan.api.model import RecipeReference


# TODO: TESTING FOR ENCODING ISSUES
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


@conan_command(group="Security", formatters={"text": format_compare_txt,
                                             "json": format_compare_json,
                                             "html": format_compare_html})
def compare(conan_api: ConanAPI, parser, *args):
    """
    Command to get the diff between versions
    """

    parser.add_argument("-op", "--old-path", help="Path to the old recipe")
    parser.add_argument("-or", "--old-reference", help='Old reference "mylib/1.0"')

    parser.add_argument("-np", "--new-path", help="Path to the new recipe")
    parser.add_argument("-nr", "--new-reference", help='New reference "mylib/1.0"')

    parser.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')

    args = parser.parse_args(*args)

    cwd = os.getcwd()
    enabled_remotes = conan_api.remotes.list(args.remote or "*")

    def _download_ref_from_remote(reference):
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

    def _export_recipe_from_path(path_to_conanfile, reference):
        path = conan_api.local.get_conanfile_path(path_to_conanfile, cwd, py=True)
        ref = RecipeReference.loads(reference)
        export_ref, conanfile = conan_api.export.export(path=path,
                                                        name=ref.name, version=ref.version,
                                                        user=ref.user, channel=ref.channel,
                                                        lockfile=None,
                                                        remotes=enabled_remotes)
        cache_path = conan_api.cache.export_path(export_ref)
        return export_ref, cache_path

    def _source(path_to_conanfile, reference):
        if path_to_conanfile is None:
            export_ref, cache_path = _download_ref_from_remote(reference)
        else:
            export_ref, cache_path = _export_recipe_from_path(path_to_conanfile, reference)
        exported_path = conan_api.local.get_conanfile_path(cache_path, cwd, py=True)
        conan_api.local.source(exported_path, name=export_ref.name, version=str(export_ref.version), user=export_ref.user,
                               channel=export_ref.channel, remotes=enabled_remotes)
        return export_ref, cache_path

    old_export_ref, old_cache_path = _source(args.old_path, args.old_reference)
    new_export_ref, new_cache_path = _source(args.new_path, args.new_reference)

    ConanOutput().info(f"Generating diff from {old_export_ref.repr_notime()} to {new_export_ref.repr_notime()} (this might take a while)")
    # TODO: This is internal, we should use the public API, but nothing exposes functionality like this
    diff = _execute_command(f'git diff --no-index "{old_cache_path}" "{new_cache_path}"',
                            # We ignore the errors because git diff returns 1 if there are differences
                            ignore_error=True)

    return {
        "conan_api": conan_api,
        "diff": diff,
        "old_export_ref": old_export_ref,
        "new_export_ref": new_export_ref,
        "old_cache_path": old_cache_path,
        "new_cache_path": new_cache_path,
    }
