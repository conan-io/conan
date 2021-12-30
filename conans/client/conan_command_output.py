import json
import os

from conans.cli.output import ConanOutput
from conans.util.files import save


class CommandOutputer(object):

    def __init__(self):
        self._output = ConanOutput()

    def json_output(self, info, json_output, cwd):
        cwd = os.path.abspath(cwd or os.getcwd())
        if not os.path.isabs(json_output):
            json_output = os.path.join(cwd, json_output)

        def date_handler(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            else:
                raise TypeError("Unserializable object {} of type {}".format(obj, type(obj)))

        save(json_output, json.dumps(info, default=date_handler))
        self._output.writeln("")
        self._output.info("JSON file created at '%s'" % json_output)

    def print_dir_list(self, list_files, path, raw):
        if not raw:
            self._output.info("Listing directory '%s':" % path)
            self._output.info("\n".join([" %s" % i for i in list_files]))
        else:
            self._output.info("\n".join(list_files))

    def print_file_contents(self, contents, file_name, raw):
        if raw or not self._output.is_terminal:
            self._output.info(contents)
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

        self._output.info(highlight(contents, lexer, TerminalFormatter()))
