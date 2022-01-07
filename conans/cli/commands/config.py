import json

from conans.cli.command import conan_command, COMMAND_GROUPS, conan_subcommand
from conans.cli.output import ConanOutput
from conans.model.conf import DEFAULT_CONFIGURATION
from conans.util.config_parser import get_bool_from_text


@conan_command(group=COMMAND_GROUPS['consumer'])
def config(conan_api, parser, *args):
    """
    Computes a dependency graph, without  installing or building the binaries
    """


def format_remote_install_configs(remote_install_configs):
    return json.dumps(remote_install_configs, indent=4)


@conan_subcommand()
def config_remote_install(conan_api, parser, subparser, *args):
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
    conan_api.config.remote_install(args.item, verify_ssl, args.type, args.args,
                                    source_folder=args.source_folder,
                                    target_folder=args.target_folder)


@conan_subcommand()
def config_remote_reinstall(conan_api, parser, subparser, *args):
    """
    Re-installs previously defined configuration (remotes, profiles, conf), from git, http or folder
    """
    conan_api.config.remote_reinstall()


@conan_subcommand()
def config_remote_list(conan_api, parser, subparser, *args):
    """
    Returns the defined origins of configuration
    """
    configs = conan_api.config.remote_list()
    for index, remote_config in enumerate(configs):
        ConanOutput().info("%s: %s" % (index, remote_config))


@conan_subcommand()
def config_remote_remove(conan_api, parser, subparser, *args):
    """
    Returns the defined origins of configuration
    """
    subparser.add_argument("item", type=int,
                           help='Remove configuration origin by index in list (index '
                                'provided by --list argument)')
    args = parser.parse_args(*args)
    conan_api.config.remote_remove(index=args.item)
    ConanOutput().success("Removed remote-install configuration")


@conan_subcommand(formatters={"json": format_remote_install_configs})
def config_list(conan_api, parser, subparser, *args):
    """
    return available built-in [conf] configuration items
    """
    out = ConanOutput()
    out.info("Supported Conan *experimental* global.conf and [conf] properties:")
    for key, value in DEFAULT_CONFIGURATION.items():
        out.info("{}: {}".format(key, value))

    return DEFAULT_CONFIGURATION


@conan_subcommand(formatters={"text": lambda x: x})
def config_home(conan_api, parser, subparser, *args):
    """
    Gets the Conan home folder
    """
    home = conan_api.config.home()
    ConanOutput().info(f"Current Conan home: {home}")
    return home


@conan_subcommand()
def config_init(conan_api, parser, subparser, *args):
    """
    Initialize Conan home configuration: settings, conf and remotes
    """
    subparser.add_argument("-f", "--force", action='store_true',
                           help="Force the removal of config if exists")
    args = parser.parse_args(*args)
    home = conan_api.config.init(force=args.force)
    return home
