from conan.api.output import cli_out_write
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.formatters import default_json_formatter
from conans.model.conf import BUILT_IN_CONFS
from conans.util.config_parser import get_bool_from_text


@conan_command(group='Consumer')
def config(conan_api, parser, *args):
    """
    Manage the Conan configuration in the Conan home.
    """


@conan_subcommand()
def config_install(conan_api, parser, subparser, *args):
    """
    Install the configuration (remotes, profiles, conf), from git, http or a folder, into the
    Conan home folder.
    """
    subparser.add_argument("item",
                           help="git repository, local file or folder or zip file (local or "
                                "http) where the configuration is stored")

    ssl_subgroup = subparser.add_mutually_exclusive_group()
    ssl_subgroup.add_argument("--verify-ssl", nargs="?", default="True",
                              help='Verify SSL connection when downloading file')
    ssl_subgroup.add_argument("--insecure", action="store_false", default=None,
                              help="Allow insecure server connections when using SSL. "
                                   "Equivalent to --verify-ssl=False",
                              dest="verify_ssl")
    subparser.add_argument("-t", "--type", choices=["git", "dir", "file", "url"],
                           help='Type of remote config')
    subparser.add_argument("-a", "--args",
                           help='String with extra arguments for "git clone"')
    subparser.add_argument("-sf", "--source-folder",
                           help='Install files only from a source subfolder from the '
                                'specified origin')
    subparser.add_argument("-tf", "--target-folder",
                           help='Install to that path in the conan cache')
    args = parser.parse_args(*args)
    verify_ssl = args.verify_ssl if isinstance(args.verify_ssl, bool) else get_bool_from_text(args.verify_ssl)
    conan_api.config.install(args.item, verify_ssl, args.type, args.args,
                             source_folder=args.source_folder,
                             target_folder=args.target_folder)


def list_text_formatter(confs):
    for k, v in confs.items():
        cli_out_write(f"{k}: {v}")


@conan_subcommand(formatters={"text": cli_out_write})
def config_home(conan_api, parser, subparser, *args):
    """
    Show the Conan home folder.
    """
    parser.parse_args(*args)
    return conan_api.config.home()


@conan_subcommand(formatters={"text": list_text_formatter, "json": default_json_formatter})
def config_list(conan_api, parser, subparser, *args):
    """
    Show all the Conan available configurations: core and tools.
    """
    parser.parse_args(*args)
    return BUILT_IN_CONFS


@conan_subcommand(formatters={"text": list_text_formatter, "json": default_json_formatter})
def config_show(conan_api, parser, subparser, *args):
    """
    Get the value of the specified conf
    """
    subparser.add_argument('pattern', help='Conf item(s) pattern for which to query their value')
    args = parser.parse_args(*args)

    return conan_api.config.show(args.pattern)
