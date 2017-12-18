import os
import json
import sys
import six
from six import StringIO

from pylint.reporters.json import JSONReporter
from pylint.lint import Run

from conans.client.output import Color
from conans.errors import ConanException


def conan_linter(conanfile_path, out):
    apply_lint = os.environ.get("CONAN_RECIPE_LINTER", True)
    if not apply_lint or apply_lint == "False":
        return
    try:
        dirname = os.path.dirname(conanfile_path)
        sys.path.append(dirname)
        py3_msgs = _lint_py3(conanfile_path)
        if py3_msgs:
            out.writeln("Python 3 incompatibilities\n    ERROR: %s"
                        % "\n    ERROR: ".join(py3_msgs),
                        front=Color.BRIGHT_MAGENTA)
        msgs = _normal_linter(conanfile_path)
        if msgs:
            out.writeln("Linter warnings\n    WARN: %s" % "\n    WARN: ".join(msgs),
                        front=Color.MAGENTA)
        pylint_werr = os.environ.get("CONAN_PYLINT_WERR", None)
        if pylint_werr and (py3_msgs or msgs):
            raise ConanException("Package recipe has linter errors. Please fix them.")
    finally:
        sys.path.pop()


class _WritableObject(object):
    def __init__(self):
        self.content = []

    def write(self, st):
        self.content.append(st)


def _runner(args):
    try:
        output = _WritableObject()
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


def _lint_py3(conanfile_path):
    if six.PY3:
        return

    args = ['--py3k', "--reports=no", "--disable=no-absolute-import", "--persistent=no",
            conanfile_path]

    output_json = _runner(args)

    result = []
    for msg in output_json:
        if msg.get("type") in ("warning", "error"):
            result.append("Py3 incompatibility. Line %s: %s"
                          % (msg.get("line"), msg.get("message")))
    return result


def _normal_linter(conanfile_path):
    args = ["--reports=no", "--disable=no-absolute-import", "--persistent=no", conanfile_path]
    pylintrc = os.environ.get("CONAN_PYLINTRC", None)
    if pylintrc:
        if not os.path.exists(pylintrc):
            raise ConanException("File %s defined by PYLINTRC doesn't exist" % pylintrc)
        args.append('--rcfile=%s' % pylintrc)

    output_json = _runner(args)

    dynamic_fields = ("source_folder", "build_folder", "package_folder", "info_build",
                      "build_requires", "info")

    def _accept_message(msg):
        symbol = msg.get("symbol")
        text = msg.get("message")
        if symbol == "no-member":
            for field in dynamic_fields:
                if field in text:
                    return False
        if symbol == "not-callable" and "self.copy is not callable" == text:
            return False
        if symbol in ("bare-except", "broad-except"):  # No exception type(s) specified
            return False
        return True

    result = []
    for msg in output_json:
        if msg.get("type") in ("warning", "error"):
            if _accept_message(msg):
                result.append("Linter. Line %s: %s" % (msg.get("line"), msg.get("message")))

    return result
