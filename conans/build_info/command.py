import argparse
import json
import os
import sys

from conans.build_info.conan_build_info import get_build_info
from conans.build_info.build_info import start_build_info, stop_build_info, create_build_info, \
    update_build_info, publish_build_info
from conans.errors import ConanException
from conans.util.files import save
from conans.client.output import ConanOutput


class ArgumentParserError(Exception):
    pass


class ErrorCatchingArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            raise ArgumentParserError(message)

    def error(self, message):
        raise ArgumentParserError(message)


def run():
    parser = argparse.ArgumentParser(description='Extracts build-info from a specified '
                                                 'conan trace log and return a valid JSON')
    parser.add_argument('trace_path', help='Path to the conan trace log file e.g.: '
                                           '/tmp/conan_trace.log')
    parser.add_argument("--output", default=False,
                        help='Optional file to output the JSON contents, if not specified the JSON'
                             ' will be printed to stdout')

    args = parser.parse_args()

    if not os.path.exists(args.trace_path):
        print("Error, conan trace log not found! '%s'" % args.trace_path)
        exit(1)
    if args.output and not os.path.exists(os.path.dirname(args.output)):
        print("Error, output file directory not found! '%s'" % args.trace_path)
        exit(1)

    try:
        info = get_build_info(args.trace_path)
        the_json = json.dumps(info.serialize())
        if args.output:
            save(args.output, the_json)
        else:
            print(the_json)
    except Exception as exc:
        print(exc)
        exit(1)


def runv2():
    output = ConanOutput(sys.stdout, sys.stderr, True)
    parser_v2 = argparse.ArgumentParser(
        description="Generates build info build info from lockfiles information",
        prog="conan_build_info")
    subparsers = parser_v2.add_subparsers(dest="subcommand", help="sub-command help")
    parser_start = subparsers.add_parser("start",
                                         help="Command to incorporate to the "
                                              "artifacts.properties the build name and number")
    parser_start.add_argument("build_name", type=str, help="build name to assign")
    parser_start.add_argument("build_number", type=int, help="build number to assign")

    parser_stop = subparsers.add_parser("stop",
                                        help="Command to remove from the artifacts.properties "
                                             "the build name and number")

    parser_create = subparsers.add_parser("create",
                                          help="Command to generate a build info json from a "
                                               "lockfile")
    parser_create.add_argument("build_info_file", type=str,
                               help="build info json for output")
    parser_create.add_argument("--lockfile", type=str, required=True, help="input lockfile")
    parser_create.add_argument("--multi-module", nargs="?", default=True,
                               help="if enabled, the module_id will be identified by the "
                                    "recipe reference plus the package ID")
    parser_create.add_argument("--skip-env", nargs="?", default=True,
                               help="capture or not the environment")
    parser_create.add_argument("--user", type=str, nargs="?", default=None, help="user")
    parser_create.add_argument("--password", type=str, nargs="?", default=None, help="password")
    parser_create.add_argument("--apikey", type=str, nargs="?", default=None, help="apikey")

    parser_update = subparsers.add_parser("update",
                                          help="Command to update a build info json with another one")
    parser_update.add_argument("buildinfo", nargs="+", help="buildinfo files to merge")
    parser_update.add_argument("--output-file", default="buildinfo.json",
                               help="path to generated build info file")

    parser_publish = subparsers.add_parser("publish",
                                           help="Command to publish the build info to Artifactory")
    parser_publish.add_argument("buildinfo", type=str,
                                help="build info to upload")
    parser_publish.add_argument("--url", type=str, required=True, help="url")
    parser_publish.add_argument("--user", type=str, nargs="?", default=None, help="user")
    parser_publish.add_argument("--password", type=str, nargs="?", default=None, help="password")
    parser_publish.add_argument("--apikey", type=str, nargs="?", default=None, help="apikey")

    def check_credential_arguments():
        if args.user and args.apikey:
            parser_v2.error("Please select one authentificacion method --user USER "
                            "--password PASSWORD or --apikey APIKEY")
        if args.user and not args.password:
            parser_v2.error(
                "Please specify a password for user '{}' with --password PASSWORD".format(
                    args.user))

    try:
        args = parser_v2.parse_args()
        if args.subcommand == "start":
            start_build_info(output, args.build_name, args.build_number)
        if args.subcommand == "stop":
            stop_build_info(output)
        if args.subcommand == "create":
            check_credential_arguments()
            create_build_info(output, args.build_info_file, args.lockfile, args.multi_module,
                              args.skip_env, args.user, args.password, args.apikey)
        if args.subcommand == "update":
            update_build_info(args.buildinfo, args.output_file)
        if args.subcommand == "publish":
            check_credential_arguments()
            publish_build_info(args.buildinfo, args.url, args.user, args.password,
                               args.apikey)
    except ArgumentParserError as exc:
        output.error(str(exc))
        parser_v2.print_help()
    except ConanException as exc:
        output.error(exc)
    except Exception as exc:
        output.error(exc)


if __name__ == "__main__":
    print("NEW CONAN_BUILD_INFO")
    if sys.argv[1] == "--version2":
        sys.argv.pop(1)
        runv2()
    else:
        run()
