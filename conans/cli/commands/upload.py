import json

from conans.cli.cli import cli_out_write
from conans.cli.command import conan_command, OnceArgument


def output_upload_cli(info):
    for uploaded_reference in info["uploaded_references"]:
        cli_out_write("{}".format(uploaded_reference))


def output_upload_json(info):
    myjson = json.dumps(info, indent=4)
    cli_out_write(myjson)


@conan_command(group="Creator commands", formatters={"cli": output_upload_cli,
                                                     "json": output_upload_json}, pipeable=True)
def upload(conan_api, parser, *args, **kwargs):
    """
    Uploads a recipe and binary packages to a remote.

    If no remote is specified, the first configured remote will be used.
    """

    parser.add_argument("pattern_or_reference", help="Pattern, recipe reference or package "
                                                     "reference e.g., 'boost/*', 'MyPackage/1.2@user/channel', "
                                                     "'MyPackage/1.2@user/channel:af7901d8bdfde621d086181aa1c495c25a17b137'",
                        nargs="?")
    parser.add_argument("-r", "--remote", action=OnceArgument,
                        help="Upload to this specific remote")
    # TODO: could upload --query be substituted by search --query | upload ?
    parser.add_argument("--query", default=None, action=OnceArgument,
                        help="Only upload packages matching a specific query. "
                             "Packages query: 'os=Windows AND (arch=x86 OR"
                             "compiler=gcc)'. The 'pattern_or_reference' parameter"
                             "has to be a reference: MyPackage/1.2@user/channel")
    parser.add_argument("--all", action="store_true", default=False,
                        help="Upload both package recipe and packages")
    args = parser.parse_args(*args)
    if not args.pattern_or_reference and not args.pipe:
        parser.error("Please specify at least the pattern to upload or pipe the input from another "
                     "command")
    pattern_or_reference = args.pipe.read().strip() if args.pipe else args.pattern_or_reference
    info = conan_api.upload(pattern_or_reference, args.remote, args.query, args.all)
    return info
