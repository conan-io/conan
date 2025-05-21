import os

from conan.api.output import ConanOutput
from conan.cli.formatters.compare.compare import format_compare_html, format_compare_txt, \
    format_compare_json
from conan.errors import ConanException
from conan.api.conan_api import ConanAPI
from conan.cli.command import conan_command, conan_subcommand
from conan.api.model import RecipeReference
from conan.internal.conan_app import ConanApp
from conan.internal.errors import conanfile_exception_formatter
from conan.internal.graph.graph import CONTEXT_HOST
from conan.internal.graph.profile_node_definer import initialize_conanfile_profile
from conan.internal.source import retrieve_exports_sources, config_source
from conan.internal.util.files import rmdir


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


@conan_command(group="Security")
def report(conan_api: ConanAPI, parser, *args):
    """
    Gets information about the recipe and its sources.
    """



@conan_subcommand(formatters={"text": format_compare_txt,
                              "json": format_compare_json,
                              "html": format_compare_html})
def report_diff(conan_api, parser, subparser, *args):
    """
    Get the difference between two recipes with their sources.
    It can be used to compare two different versions of the same recipe, or two different recipe revisions.

    Each old/new recipe can be specified by a path to a conanfile.py and a companion reference,
    or by a reference only.

    If only a reference is specified, it will be searched in the local cache,
    or downloaded from the specified remotes. If no revision is specified, the latest revision will be used.
    """

    ref_help = ("{type} reference, e.g. 'mylib/1.0'. "
                "If used on its own, it can contain a revision, which will be resolved to the latest one if not provided, "
                "but it will be ignored if a path is specified. "
                "If used with a path, it will be used to create the reference for the recipe to be compared.")

    subparser.add_argument("-op", "--old-path", help="Path to the old recipe if comparing a local recipe is desired")
    subparser.add_argument("-or", "--old-reference", help=ref_help.format(type="Old"), required=True)

    subparser.add_argument("-np", "--new-path", help="Path to the new recipe if comparing a local recipe is desired")
    subparser.add_argument("-nr", "--new-reference", help=ref_help.format(type="New"), required=True)

    subparser.add_argument("-r", "--remote", action="append", default=None,
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
                                                        name=ref.name, version=str(ref.version),
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
        _configure_source(conan_api, exported_path, export_ref, enabled_remotes)
        return export_ref, cache_path

    old_export_ref, old_cache_path = _source(args.old_path, args.old_reference)
    new_export_ref, new_cache_path = _source(args.new_path, args.new_reference)

    old_diff_path = os.path.abspath(os.path.join(old_cache_path, os.path.pardir)).replace("\\", "/")
    new_diff_path = os.path.abspath(os.path.join(new_cache_path, os.path.pardir)).replace("\\", "/")

    ConanOutput().info(f"Generating diff from {old_export_ref.repr_notime()} to {new_export_ref.repr_notime()} (this might take a while)")
    ConanOutput().info(f'git diff --no-index "{old_diff_path}" "{new_diff_path}"')
    # TODO: This is internal, we should use the public API, but nothing exposes functionality like this
    diff = _execute_command(f'git diff --no-index "{old_diff_path}" "{new_diff_path}"',
                            # We ignore the errors because git diff returns 1 if there are differences
                            ignore_error=True)

    if args.old_path:
        conan_api.remove.recipe(old_export_ref)
    if args.new_path:
        conan_api.remove.recipe(new_export_ref)

    return {
        "conan_api": conan_api,
        "diff": diff,
        "old_export_ref": old_export_ref,
        "new_export_ref": new_export_ref,
        "old_cache_path": old_diff_path,
        "new_cache_path": new_diff_path,
    }
