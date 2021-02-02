import textwrap
from collections import OrderedDict

from conans.util.files import save

PLACEHOLDER = "$CONANVARPLACEHOLDER%"


class EnvironmentItem:

    def __init__(self, value=None, separator=None):
        self._value = value
        self._separator = separator

    def value(self, placeholder):
        value = [v if v != PLACEHOLDER else placeholder for v in self._value]
        value = self._separator.join(value) if value else ""
        return value

    def copy(self):
        return EnvironmentItem(self._value[:], self._separator)

    def define(self, value, separator=" "):
        self._value = value if isinstance(value, list) else [value]
        self._separator = separator

    def append(self, value, separator=" "):
        value = value if isinstance(value, list) else [value]
        self._value = [PLACEHOLDER] + value
        self._separator = separator

    def prepend(self, value, separator=" "):
        value = value if isinstance(value, list) else [value]
        self._value = value + [PLACEHOLDER]
        self._separator = separator

    def clean(self):
        self._value = []
        self._separator = None

    def update(self, other):
        """
       :type other: EnvironmentItem
       """
        result = other._value
        try:
            index = result.index(PLACEHOLDER)
            result[index:index+1] = self._value
            assert self._separator == other._separator
        except ValueError:
            pass
        self._value = result
        self._separator = other._separator


class Environment:
    def __init__(self):
        # It being ordered allows for Windows case-insensitive composition
        self._values = OrderedDict()

    def __getitem__(self, name):
        return self._values.setdefault(name, EnvironmentItem())

    def save_bat(self, filename, generate_deactivate=True):
        deactivate = textwrap.dedent("""\
            echo Capturing current environment in deactivate_{filename}
            setlocal
            echo @echo off > "deactivate_{filename}"
            echo echo Restoring environment >> "deactivate_{filename}"
            for %%v in ({vars}) do (
                set foundenvvar=
                for /f "delims== tokens=1,2" %%a in ('set') do (
                    if "%%a" == "%%v" (
                        echo set %%a=%%b>> "deactivate_{filename}"
                        set foundenvvar=1
                    )
                )
                if not defined foundenvvar (
                    echo set %%v=>> "deactivate_{filename}"
                )
            )
            endlocal

            """).format(filename=filename, vars=" ".join(self._values.keys()))
        capture = textwrap.dedent("""\
            @echo off
            {deactivate}
            echo Configuring environment variables
            """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for k, v in self._values.items():
            value = v.value("%{}%".format(k))
            result.append('set {}={}'.format(k, value))

        content = "\n".join(result)
        save(filename, content)

    def save_sh(self, filename):
        capture = textwrap.dedent("""\
            echo Capturing current environment in deactivate_{filename}
            echo echo Restoring variables >> deactivate_{filename}
            for v in {vars}
            do
                value=${{!v}}
                if [ -n "$value" ]
                then
                    echo export "$v=$value" >> deactivate_{filename}
                else
                    echo unset $v >> deactivate_{filename}
                fi
            done
            echo Configuring environment variables
            """.format(filename=filename, vars=" ".join(self._values.keys())))
        result = [capture]
        for k, v in self._values.items():
            value = v.value("${}".format(k))
            if value:
                result.append('export {}="{}"'.format(k, value))
            else:
                result.append('unset {}'.format(k))

        content = "\n".join(result)
        save(filename, content)

    def compose(self, other):
        """
        :type other: Environment
        """
        result = Environment()
        result._values = OrderedDict([(k, v.copy()) for k, v in self._values.items()])
        for k, v in other._values.items():
            v = v.copy()
            existing = result._values.get(k)
            if existing is None:
                result._values[k] = v
            else:
                existing.update(v)
        return result
