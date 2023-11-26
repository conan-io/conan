from conan.api.conan_api import ConanAPI
from conan.api.model import MultiPackagesList
from conan.api.output import ConanOutput
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.commands.list import print_list_json, print_list_compact


@conan_command(group="Consumer")
def listx(conan_api, parser, *args):
    """
    eXtended list commands.
    """


@conan_subcommand(formatters={"text": print_list_compact,
                              "json": print_list_json})
def listx_find_binaries(conan_api: ConanAPI, parser,  subparser, *args):
    """
    List existing recipes, revisions, or packages in the cache (by default) or the remotes.
    """
    subparser.add_argument('ref',
                           help="A pattern in the form 'pkg/version#revision:package_id#revision', "
                                "e.g: zlib/1.2.13:* means all binaries for zlib/1.2.13. "
                                "If revision is not specified, it is assumed latest one.")
    subparser.add_argument('-pr', '--profile', default=None, action="append",
                           help="Profiles to filter the package binaries")
    subparser.add_argument("-r", "--remote", default=None, action="append",
                           help="Remote names. Accepts wildcards ('*' means all the remotes available)")
    subparser.add_argument("-c", "--cache", action='store_true', help="Search in the local cache")

    args = parser.parse_args(*args)

    # If neither remote nor cache are defined, show results only from cache
    pkglist = MultiPackagesList()
    profile = conan_api.profiles.get_profile(args.profile) if args.profile else None
    if args.cache or not (args.cache or args.remote):
        try:
            ConanOutput().info(f"Finding binaries in the cache")
            cache_list = conan_api.list.find_binaries(args.ref, remote=None, profile=profile)
        except Exception as e:
            print(e)
            pkglist.add_error("Local Cache", str(e))
        else:
            pkglist.add("Local Cache", cache_list)
    if args.remote or not (args.cache or args.remote):
        remotes = conan_api.remotes.list(args.remote)
        for remote in remotes:
            try:
                ConanOutput().info(f"Finding binaries in remote {remote.name}")
                remote_list = conan_api.list.find_binaries(args.ref, remote=remote, profile=profile)
            except Exception as e:
                pkglist.add_error(remote.name, str(e))
            else:
                pkglist.add(remote.name, remote_list)

    return {
        "results": pkglist.serialize(),
        "conan_api": conan_api
    }
