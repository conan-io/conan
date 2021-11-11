from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, Extender


@conan_command(group=COMMAND_GROUPS['creator'])
def remove(conan_api: ConanAPIV2, parser, *args, **kwargs):
    """
    Removes recipes and packages locally or in a remote server
    """
    parser.add_argument("reference", help="Reference for a recipe or a package. It admit patterns "
                                          "with * (fnmatch)")
    parser.add_argument("--pkg-query", "-q",
                        help="Packages query: 'os=Windows AND (arch=x86 OR compiler=gcc)'. "
                             "When specified, the recipe won't be removed, only the packages "
                             "matching the query. Use 'True' to remove all the packages.")
    parser.add_argument("-r", "--remote",  action=Extender, help="Remote names")
    args = parser.parse_args(*args)
    print(args)
