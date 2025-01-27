import json
import os
from collections import OrderedDict

from conan.api.conan_api import ConanAPI
from conan.api.input import UserInput
from conan.api.model import Remote, LOCAL_RECIPES_INDEX
from conan.api.output import cli_out_write, Color, ConanOutput
from conan.api.subapi.audit import CONAN_CENTER_CATALOG_NAME
from conan.cli import make_abs_path
from conan.cli.args import common_graph_args, validate_common_graph_args
from conan.cli.command import conan_command, conan_subcommand, OnceArgument
from conan.cli.commands.list import remote_color, error_color, recipe_color, \
    reference_color
from conan.cli.printers import print_profiles
from conan.cli.printers.graph import print_graph_basic
from conan.errors import ConanException
from conans.client.rest.remote_credentials import RemoteCredentials


def _add_provider_arg(subparser):
    subparser.add_argument("-p", "--provider", help="Provider to use for scanning")


def text_vuln_formatter(data_json):
    from conan.api.output import cli_out_write, Color

    severity_colors = {
        "Critical": Color.BRIGHT_RED,
        "High": Color.RED,
        "Medium": Color.BRIGHT_YELLOW,
        "Low": Color.BRIGHT_CYAN
    }
    severity_order = {
        "Critical": 4,
        "High": 3,
        "Medium": 2,
        "Low": 1
    }

    def wrap_and_indent(txt, limit=80, indent=2):
        txt = txt.replace("\n", " ").strip()
        if len(txt) <= limit:
            return " " * indent + txt
        lines = []
        while len(txt) > limit:
            split_index = txt.rfind(" ", 0, limit)
            if split_index == -1:
                split_index = limit
            lines.append(" " * indent + txt[:split_index].strip())
            txt = txt[split_index:].strip()
        lines.append(" " * indent + txt)
        return "\n".join(lines)

    if not data_json or "data" not in data_json or not data_json["data"]:
        cli_out_write("No vulnerabilities found.\n", fg=Color.BRIGHT_GREEN)
        return

    total_vulns = 0
    summary_lines = []

    for pkg_name, pkg_info in data_json["data"].items():
        ref = f"{pkg_name}/{pkg_info['version']}"
        edges = pkg_info.get("vulnerabilities", {}).get("edges", [])
        count = len(edges)

        border_line = "*" * (len(ref) + 4)
        cli_out_write("\n" + border_line, fg=Color.BRIGHT_WHITE)
        cli_out_write(f"* {ref} *", fg=Color.BRIGHT_WHITE)
        cli_out_write(border_line, fg=Color.BRIGHT_WHITE)

        if not count:
            cli_out_write("\nNo vulnerabilities found.\n", fg=Color.BRIGHT_GREEN)
            continue

        total_vulns += count
        summary_lines.append(f"{ref} {count} {'vulnerability' if count == 1 else 'vulnerabilities'} found")
        cli_out_write(f"\n{count} {'vulnerability' if count == 1 else 'vulnerabilities'} found:\n", fg=Color.BRIGHT_YELLOW)

        sorted_vulns = sorted(edges, key=lambda v: -severity_order.get(v["node"].get("severity", "Medium"), 2))

        for vuln in sorted_vulns:
            node = vuln["node"]
            name = node["name"]
            sev = node.get("severity", "Medium")
            sev_color = severity_colors.get(sev, Color.BRIGHT_YELLOW)
            score = node.get("cvss", {}).get("preferredBaseScore")
            score_txt = f", CVSS: {score}" if score else ""
            desc = node.get("description", "")
            desc = (desc[:240] + "...") if len(desc) > 240 else desc
            desc_wrapped = wrap_and_indent(desc)

            cli_out_write(f"- {name}", fg=Color.BRIGHT_WHITE, endline="")
            cli_out_write(f" (Severity: {sev}{score_txt})", fg=sev_color)
            cli_out_write("\n" + desc_wrapped)

            references = node.get("references")
            if references:
                cli_out_write(f"  url: {references[0]}", fg=Color.BRIGHT_BLUE)
            cli_out_write("")

    color_for_total = Color.BRIGHT_RED if total_vulns else Color.BRIGHT_GREEN
    cli_out_write(f"Total vulnerabilities found: {total_vulns}\n", fg=color_for_total)

    cli_out_write("\nSummary:\n", fg=Color.BRIGHT_WHITE)
    for line in summary_lines:
        cli_out_write(f"- {line}", fg=Color.BRIGHT_WHITE)

    cli_out_write(
        "\nVulnerability information provided by JFrog (https://jfrog.com/help/r/jfrog-catalog/jfrog-catalog)\n",
        fg=Color.BRIGHT_WHITE
    )

def json_vuln_formatter(data):
    cli_out_write(json.dumps(data, indent=4))

@conan_subcommand(formatters={"text": text_vuln_formatter, "json": json_vuln_formatter})
def audit_scan(conan_api: ConanAPI, parser, subparser, *args):
    """
    Scan a given recipe for vulnerabilities in its dependencies.
    """
    common_graph_args(subparser)
    # TODO: Might not be needed?
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the provided path is a build-require')
    _add_provider_arg(subparser)
    args = parser.parse_args(*args)

    # This comes from install command

    validate_common_graph_args(args)
    # basic paths
    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=None) if args.path else None

    # Basic collaborators: remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    overrides = eval(args.lockfile_overrides) if args.lockfile_overrides else None
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile, conanfile_path=path, cwd=cwd,
                                               partial=args.lockfile_partial, overrides=overrides)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)
    print_profiles(profile_host, profile_build)

    # Graph computation (without installation of binaries)
    gapi = conan_api.graph
    if path:
        deps_graph = gapi.load_graph_consumer(path, args.name, args.version, args.user, args.channel,
                                              profile_host, profile_build, lockfile, remotes,
                                              args.update, is_build_require=args.build_require)
    else:
        deps_graph = gapi.load_graph_requires(args.requires, args.tool_requires, profile_host,
                                              profile_build, lockfile, remotes, args.update)
    print_graph_basic(deps_graph)
    deps_graph.report_graph_error()

    if deps_graph.error:
        return {"error": deps_graph.error}

    provider = conan_api.audit.get_provider(args.provider or CONAN_CENTER_CATALOG_NAME)
    vulnerabilities = conan_api.audit.scan(deps_graph, provider)

    return vulnerabilities


@conan_subcommand(formatters={"text": text_vuln_formatter, "json": json_vuln_formatter})
def audit_list(conan_api: ConanAPI, parser, subparser, *args):
    """
    List the vulnerabilities of the given reference.
    """
    subparser.add_argument("reference", help="Reference to list vulnerabilities for", nargs="?")
    subparser.add_argument("--sbom", help="Path to the SBOM file")
    _add_provider_arg(subparser)
    args = parser.parse_args(*args)

    if args.sbom and args.reference:
        raise ConanException("Cannot use both reference and SBOM file at the same time")

    provider = conan_api.audit.get_provider(args.provider or CONAN_CENTER_CATALOG_NAME)

    if args.sbom:
        with open(args.sbom, "r") as f:
            sbom = json.load(f)
        vulnerabilities = []
        for package in sbom["components"]:
            reference = f"{package['name']}/{package['version']}"
            print(reference)
            result = conan_api.audit.list(reference, provider)
            vulnerabilities.extend(result)
    else:
        vulnerabilities = conan_api.audit.list(args.reference, provider)

    return vulnerabilities

def text_provider_formatter(providers):
    for provider in providers:
        if provider:
            cli_out_write(f"{provider.name} - {provider.url}")

def json_provider_formatter(providers):
    ret = []
    for provider in providers:
        if provider:
            ret.append({"name": provider.name, "url": provider.url})
    cli_out_write(json.dumps(ret, indent=4))


@conan_subcommand(formatters={"text": text_provider_formatter, "json": json_provider_formatter})
def audit_provider(conan_api, parser, subparser, *args):
    """ Manage providers for the audit command """
    action = subparser.add_mutually_exclusive_group(required=True)
    action.add_argument("--add", action="store_true", help="Add a provider")
    action.add_argument("--list", action="store_true", help="List all providers")
    action.add_argument("--auth", action="store_true", help="Authenticate on a provider")

    subparser.add_argument("--name", help="Provider name")
    subparser.add_argument("--url", help="Provider URL")
    subparser.add_argument("--type", help="Provider type", choices=["catalog", "private", "osv"])
    subparser.add_argument("--token", help="Provider token")
    args = parser.parse_args(*args)

    if args.add:
        if not args.name or not args.url or not args.type:
            raise ConanException("Name, URL and type are required to add a provider")
        if not args.token:
            user_input = UserInput(conan_api.config.get("core:non_interactive"))
            ConanOutput().write(f"Please enter a token for {args.name} the provider: ")
            token = user_input.get_password()
        else:
            token = args.token

        conan_api.audit.add_provider(args.name, args.url, args.type, token)
        return []
    elif args.list:
        providers = conan_api.audit.list_providers()
        return providers
    elif args.auth:
        if not args.name:
            raise ConanException("Name is required to authenticate on a provider")
        if not args.token:
            user_input = UserInput(conan_api.config.get("core:non_interactive"))
            ConanOutput().write(f"Please enter a token for {args.name} the provider: ")
            token = user_input.get_password()
        else:
            token = args.token

        provider = conan_api.audit.get_provider(args.name)
        conan_api.audit.auth_provider(provider, token)
        return [provider]

@conan_command(group="Security")
def audit(conan_api, parser, *args):
    """
    Find vulnerabilities in your dependencies.
    """
