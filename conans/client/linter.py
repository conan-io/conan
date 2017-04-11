
from pylint.reporters.json import JSONReporter
import six
from pylint.lint import Run
import json
import sys
from six import StringIO
from conans.client.output import Color
import os


class WritableObject(object):
    def __init__(self):
        self.content = []

    def write(self, st):
        self.content.append(st)


def conan_linter(conanfile_path, out):
    apply_lint = os.environ.get("CONAN_RECIPE_LINTER", True)
    if not apply_lint or apply_lint == "False":
        return
    try:
        dirname = os.path.dirname(conanfile_path)
        sys.path.append(dirname)
        py3_msgs = lint_py3(conanfile_path)
        if py3_msgs:
            out.writeln("Python 3 incompatibilities\n    ERROR: %s" % "\n    ERROR: ".join(py3_msgs),
                        front=Color.BRIGHT_MAGENTA)
        msgs = normal_linter(conanfile_path)
        if msgs:
            out.writeln("Linter warnings\n    WARN: %s" % "\n    WARN: ".join(msgs),
                        front=Color.MAGENTA)
    finally:
        sys.path.pop()


def _runner(args):
    try:
        output = WritableObject()
        stdout_ = sys.stderr
        stream = StringIO()
        sys.stderr = stream
        Run(args, reporter=JSONReporter(output), exit=False)
    finally:
        sys.stderr = stdout_
    try:
        output = "".join(output.content)
        return json.loads(output)
    except ValueError:
        return []


def lint_py3(conanfile_path):
    if six.PY3:
        return

    args = ['--py3k', "--reports=no", "--disable=no-absolute-import", "--persistent=no", conanfile_path]
    output_json = _runner(args)

    result = []
    for msg in output_json:
        if msg.get("type") in ("warning", "error"):
            result.append("Py3 incompatibility. Line %s: %s" % (msg.get("line"), msg.get("message")))
    return result


def normal_linter(conanfile_path):
    args = ["--reports=no", "--disable=no-absolute-import", "--persistent=no", conanfile_path]
    output_json = _runner(args)

    result = []
    for msg in output_json:
        if msg.get("type") in ("warning", "error"):
            if msg.get("message") != "self.copy is not callable":
                result.append("Linter. Line %s: %s" % (msg.get("line"), msg.get("message")))
    return result
