from conans.cli.command import conan_command, COMMAND_GROUPS, conan_subcommand
from conans.cli.output import ConanOutput
from conans.util.config_parser import get_bool_from_text


@conan_command(group=COMMAND_GROUPS['consumer'])
def config(conan_api, parser, *args):
    """
    Manages the Conan configuration in the current Conan home.
    """


@conan_subcommand()
def config_install(conan_api, parser, subparser, *args):
    """
    Installs the configuration (remotes, profiles, conf), from git, http or folder
    """
    subparser.add_argument("item",
                           help="git repository, local file or folder or zip file (local or "
                                "http) where the configuration is stored")

    subparser.add_argument("--verify-ssl", nargs="?", default="True",
                           help='Verify SSL connection when downloading file')
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

    verify_ssl = get_bool_from_text(args.verify_ssl)
    conan_api.config.install(args.item, verify_ssl, args.type, args.args,
                             source_folder=args.source_folder,
                             target_folder=args.target_folder)


@conan_subcommand(formatters={"text": lambda x: x})
def config_home(conan_api, parser, subparser, *args):
    """
    Gets the Conan home folder
    """
    home = conan_api.config.home()
    ConanOutput().info(f"Current Conan home: {home}")
    return home
