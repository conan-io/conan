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
