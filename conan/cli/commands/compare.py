import os

from conan.cli.formatters.compare.compare import format_compare_html, format_compare_txt
from conan.errors import ConanException
from conan.api.conan_api import ConanAPI
from conan.cli.command import conan_command
from conan.api.model import RecipeReference
from conan.internal.util.runners import check_output_runner


@conan_command(group="Security", formatters={"text": format_compare_txt,
                                             # "json": format_compare_json,  # TODO?
                                             "html": format_compare_html})
def compare(conan_api: ConanAPI, parser, *args):
    """
    Command to get the diff between versions
    """

    parser.add_argument("-op", "--old-path", help="Path to the old recipe")
    parser.add_argument("-ov", "--old-reference", help='Old reference "mylib/1.0"')
    parser.add_argument("-or", "--old-require", help='Old reference "mylib/1.0"')

    parser.add_argument("-np", "--new-path", help="Path to the new recipe")
    parser.add_argument("-nv", "--new-reference", help="New reference")
    parser.add_argument("-nr", "--new-require", help='New reference "mylib/1.0"')

    parser.add_argument("-s", "--split_diff", action="store_true")
    parser.add_argument("--encoding", default="utf-8", help="Encoding to read diff")
    parser.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')

    args = parser.parse_args(*args)

    cwd = os.getcwd()
    enabled_remotes = conan_api.remotes.list(args.remote or "*")

    def _download_ref_from_remote(reference):
        ref = RecipeReference().loads(reference)
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
            raise ConanException(f"No matching reference for {reference} in remotes")

        conan_api.download.recipe(full_ref, matching_remote)
        cache_path = conan_api.cache.export_path(ref)
        return ref, cache_path

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

    def _source(path_to_conanfile, reference, required_ref):
        if required_ref is not None:
            export_ref, cache_path = _download_ref_from_remote(required_ref)
        else:
            export_ref, cache_path = _export_recipe_from_path(path_to_conanfile, reference)
        exported_path = conan_api.local.get_conanfile_path(cache_path, cwd, py=True)
        conan_api.local.source(exported_path, name=export_ref.name, version=str(export_ref.version), user=export_ref.user,
                               channel=export_ref.channel, remotes=enabled_remotes)
        return export_ref, cache_path

    old_export_ref, old_cache_path = _source(args.old_path, args.old_reference, args.old_require)
    new_export_ref, new_cache_path = _source(args.new_path, args.new_reference, args.new_require)

    # TODO: This is internal, we should use the public API, but nothing exposes functionality like this
    diff = check_output_runner(f"git diff --no-index {old_cache_path} {new_cache_path}",
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
