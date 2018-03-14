import os
import json
import sys
import six

from conans.client.output import Color
from conans.errors import ConanException
from subprocess import PIPE, Popen
from conans import tools
from conans import __path__ as root_path


def conan_linter(conanfile_path, out):
    if getattr(sys, 'frozen', False):
        out.info("No linter available. Use a pip installed conan for recipe linting")
        return
    apply_lint = os.environ.get("CONAN_RECIPE_LINTER", True)
    if not apply_lint or apply_lint == "False":
        return

    dirname = os.path.dirname(conanfile_path)
    dir_path = os.path.dirname(root_path[0])

    with tools.environment_append({"PYTHONPATH": [dirname, dir_path]}):
        try:
            py3_msgs = _lint_py3(conanfile_path)
            msgs = _normal_linter(conanfile_path)
        except Exception as e:
            out.warn("Failed pylint: %s" % e)
        else:
            if py3_msgs:
                out.writeln("Python 3 incompatibilities\n    ERROR: %s"
                            % "\n    ERROR: ".join(py3_msgs),
                            front=Color.BRIGHT_MAGENTA)
            if msgs:
                out.writeln("Linter warnings\n    WARN: %s" % "\n    WARN: ".join(msgs),
                            front=Color.MAGENTA)
            pylint_werr = os.environ.get("CONAN_PYLINT_WERR", None)
            if pylint_werr and (py3_msgs or msgs):
                raise ConanException("Package recipe has linter errors. Please fix them.")


def _runner(args):
    command = "pylint -f json " + " ".join(args)
    # This is a bit repeated from det
    proc = Popen(command, shell=True, bufsize=1, stdout=PIPE, stderr=PIPE)
    output_buffer = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        output_buffer.append(str(line))
    proc.communicate()
    output = "".join(output_buffer)
    return json.loads(output) if output else {}


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
        if symbol == "not-callable" and "self.copy_deps is not callable" == text:
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
