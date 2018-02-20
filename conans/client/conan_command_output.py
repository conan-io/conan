import json
import os


from conans.client.printer import Printer
from conans.client.remote_registry import RemoteRegistry
from conans.util.files import save


class CommandOutputer(object):

    def __init__(self, user_io, client_cache):
        self.user_io = user_io
        self.client_cache = client_cache

    def writeln(self, value):
        self.user_io.out.writeln(value)

    def print_profile(self, profile, profile_text):
        Printer(self.user_io.out).print_profile(profile, profile_text)

    def profile_list(self, profiles):
        for p in sorted(profiles):
            self.user_io.out.info(p)

    def remote_list(self, remotes):
        for r in remotes:
            self.user_io.out.info("%s: %s [Verify SSL: %s]" % (r.name, r.url, r.verify_ssl))

    def remote_ref_list(self, refs):
        for ref, remote in refs.items():
            self.user_io.out.info("%s: %s" % (ref, remote))

    def build_order(self, info):
        msg = ", ".join(str(s) for s in info)
        self.user_io.out.info(msg)

    def json_build_order(self, info, json_output, cwd):
        data = {"groups": [[str(ref) for ref in group] for group in info]}
        json_str = json.dumps(data)
        if json_output is True:  # To the output
            self.user_io.out.write(json_str)
        else:  # Path to a file
            cwd = os.path.abspath(cwd or os.getcwd())
            if not os.path.isabs(json_output):
                json_output = os.path.join(cwd, json_output)
            save(json_output, json_str)

    def _read_dates(self, deps_graph):
        ret = {}
        for ref, _ in sorted(deps_graph.nodes):
            if ref:
                manifest = self.client_cache.load_manifest(ref)
                ret[ref] = manifest.time_str
        return ret

    def nodes_to_build(self, nodes_to_build):
        self.user_io.out.info(", ".join(nodes_to_build))

    def info(self, deps_graph, graph_updates_info, only, remote, package_filter, show_paths, project_reference):
        registry = RemoteRegistry(self.client_cache.registry, self.user_io.out)
        Printer(self.user_io.out).print_info(deps_graph, project_reference,
                                             only, registry, graph_updates_info=graph_updates_info,
                                             remote=remote, node_times=self._read_dates(deps_graph),
                                             path_resolver=self.client_cache, package_filter=package_filter,
                                             show_paths=show_paths)

    def info_graph(self, graph_filename, deps_graph, project_reference, cwd):
        if graph_filename.endswith(".html"):
            from conans.client.grapher import ConanHTMLGrapher
            grapher = ConanHTMLGrapher(project_reference, deps_graph)
        else:
            from conans.client.grapher import ConanGrapher
            grapher = ConanGrapher(project_reference, deps_graph)

        cwd = os.path.abspath(cwd or os.getcwd())
        if not os.path.isabs(graph_filename):
            graph_filename = os.path.join(cwd, graph_filename)
        grapher.graph_file(graph_filename)

    def print_search_references(self, references, pattern, raw):
        printer = Printer(self.user_io.out)
        printer.print_search_recipes(references, pattern, raw)

    def print_search_packages(self, ordered_packages, pattern, recipe_hash, packages_query, table):
        if table:
            from conans.client.grapher import html_binary_graph
            html_binary_graph(pattern, ordered_packages, recipe_hash, table)
        else:
            printer = Printer(self.user_io.out)
            printer.print_search_packages(ordered_packages, pattern, recipe_hash, packages_query)

    def print_dir_list(self, list_files, path, raw):
        if not raw:
            self.user_io.out.info("Listing directory '%s':" % path)
            self.user_io.out.writeln("\n".join([" %s" % i for i in list_files]))
        else:
            self.user_io.out.writeln("\n".join(list_files))

    def print_file_contents(self, contents, file_name, raw):
        if raw or not self.user_io.out.is_terminal:
            self.user_io.out.writeln(contents)
            return

        from pygments import highlight
        from pygments.lexers import PythonLexer, IniLexer, TextLexer
        from pygments.formatters import TerminalFormatter

        if file_name.endswith(".py"):
            lexer = PythonLexer()
        elif file_name.endswith(".txt"):
            lexer = IniLexer()
        else:
            lexer = TextLexer()

        self.user_io.out.write(highlight(contents, lexer, TerminalFormatter()))
