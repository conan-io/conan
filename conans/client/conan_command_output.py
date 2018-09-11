import json
import os


from conans.client.printer import Printer
from conans.client.remote_registry import RemoteRegistry
from conans.util.files import save
from conans.unicode import get_cwd


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

    def remote_list(self, remotes, raw):
        for r in remotes:
            if raw:
                self.user_io.out.info("%s %s %s" % (r.name, r.url, r.verify_ssl))
            else:
                self.user_io.out.info("%s: %s [Verify SSL: %s]" % (r.name, r.url, r.verify_ssl))

    def remote_ref_list(self, refs):
        for ref, remote_name in refs.items():
            self.user_io.out.info("%s: %s" % (ref, remote_name))

    def build_order(self, info):
        msg = ", ".join(str(s) for s in info)
        self.user_io.out.info(msg)

    def json_build_order(self, info, json_output, cwd):
        data = {"groups": [[str(ref) for ref in group] for group in info]}
        json_str = json.dumps(data)
        if json_output is True:  # To the output
            self.user_io.out.write(json_str)
        else:  # Path to a file
            cwd = os.path.abspath(cwd or get_cwd())
            if not os.path.isabs(json_output):
                json_output = os.path.join(cwd, json_output)
            save(json_output, json_str)

    def json_output(self, info, json_output, cwd):
        cwd = os.path.abspath(cwd or get_cwd())
        if not os.path.isabs(json_output):
            json_output = os.path.join(cwd, json_output)

        def date_handler(obj):
            return obj.isoformat() if hasattr(obj, 'isoformat') else obj

        save(json_output, json.dumps(info, default=date_handler))
        self.user_io.out.writeln("")
        self.user_io.out.info("JSON file created at '%s'" % json_output)

    def _read_dates(self, deps_graph):
        ret = {}
        for node in sorted(deps_graph.nodes):
            ref = node.conan_ref
            if ref:
                manifest = self.client_cache.load_manifest(ref)
                ret[ref] = manifest.time_str
        return ret

    def nodes_to_build(self, nodes_to_build):
        self.user_io.out.info(", ".join(str(n) for n in nodes_to_build))

    def info(self, deps_graph, only, package_filter, show_paths):
        registry = RemoteRegistry(self.client_cache.registry, self.user_io.out)
        Printer(self.user_io.out).print_info(deps_graph,
                                             only, registry,
                                             node_times=self._read_dates(deps_graph),
                                             path_resolver=self.client_cache, package_filter=package_filter,
                                             show_paths=show_paths)

    def info_graph(self, graph_filename, deps_graph, cwd):
        if graph_filename.endswith(".html"):
            from conans.client.graph.grapher import ConanHTMLGrapher
            grapher = ConanHTMLGrapher(deps_graph)
        else:
            from conans.client.graph.grapher import ConanGrapher
            grapher = ConanGrapher(deps_graph)

        cwd = os.path.abspath(cwd or get_cwd())
        if not os.path.isabs(graph_filename):
            graph_filename = os.path.join(cwd, graph_filename)
        grapher.graph_file(graph_filename)

    def print_search_references(self, search_info, pattern, raw, all_remotes_search):
        printer = Printer(self.user_io.out)
        printer.print_search_recipes(search_info, pattern, raw, all_remotes_search)

    def print_search_packages(self, search_info, reference, packages_query, table,
                                outdated=False):
        if table:
            from conans.client.graph.grapher import html_binary_graph
            html_binary_graph(search_info, reference, table)
        else:
            printer = Printer(self.user_io.out)
            printer.print_search_packages(search_info, reference, packages_query,
                                          outdated=outdated)

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

    def print_user_list(self, info):
        for remote in info["remotes"]:
            authenticated = " [Authenticated]" if remote["authenticated"] else ""
            anonymous = " (anonymous)" if not remote["user_name"] else ""
            self.user_io.out.info("Current user of remote '%s' set to: '%s'%s%s" %
                                  (remote["name"], str(remote["user_name"]), anonymous,
                                   authenticated))

    def print_user_set(self, remote_name, prev_user, user):
        previous_username = prev_user or "None"
        previous_anonymous = " (anonymous)" if not prev_user else ""
        username = user or "None"
        anonymous = " (anonymous)" if not user else ""

        if prev_user == user:
            self.user_io.out.info("User of remote '%s' is already '%s'%s" %
                                  (remote_name, previous_username, previous_anonymous))
        else:
            self.user_io.out.info("Changed user of remote '%s' from '%s'%s to '%s'%s" %
                                  (remote_name, previous_username, previous_anonymous, username,
                                   anonymous))
