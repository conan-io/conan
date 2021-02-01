import textwrap

from conans.errors import ConanException
from conans.util.files import save


class EnvironmentItem:
    APPEND = "append"
    DEFINE = "define"
    PREPEND = "prepend"
    CLEAN = "clean"

    def __init__(self, action=None, value=None, separator=None):
        self.action = action
        self.value = value
        self.separator = separator

    def define(self, value, separator=" "):
        self.value = value if isinstance(value, list) else [value]
        self.separator = separator
        self.action = EnvironmentItem.DEFINE

    def append(self, value, separator=" "):
        self.define(value, separator)
        self.action = EnvironmentItem.APPEND

    def prepend(self, value, separator=" "):
        self.define(value, separator)
        self.action = EnvironmentItem.PREPEND

    def clean(self):
        self.define(None)
        self.action = EnvironmentItem.CLEAN

    def copy(self):
        result = EnvironmentItem(self.action, self.value[:], self.separator)
        return result

    def update(self, other):
        if other.action in (EnvironmentItem.CLEAN, EnvironmentItem.DEFINE):
            self.action = other.action
            self.value = other.value
            self.separator = other.separator
            return
        elif other.action == EnvironmentItem.APPEND:
            if self.action == EnvironmentItem.CLEAN:
                self.action = EnvironmentItem.DEFINE
                self.value = other.value
                self.separator = other.separator
            elif self.action in (EnvironmentItem.DEFINE, EnvironmentItem.APPEND):
                self.value.extend(other.value)
                assert self.separator == other.separator
            else:
                raise ConanException("Variable  was 'prepend' cannot 'append' now")
        elif other.action == EnvironmentItem.PREPEND:
            if self.action == EnvironmentItem.CLEAN:
                self.action = EnvironmentItem.DEFINE
                self.value = other.value
                self.separator = other.separator
            elif self.action in (EnvironmentItem.DEFINE, EnvironmentItem.PREPEND):
                self.value = other.value + self.value
                assert self.separator == other.separator
            else:
                raise ConanException("Variable  was 'append' cannot 'prepend' now")


class Environment:
    def __init__(self):
        self._values = {}

    def __getitem__(self, name):
        return self._values.setdefault(name, EnvironmentItem())

    def vars(self):
        return list(self._values.keys())

    def dumps(self):
        result = []
        for k, v in self._values.items():
            result.append('{} {} "{}" {}'.format(k, v.action, v.separator, v.value))
        return "\n".join(result)

    def save_bat(self, filename):
        capture = textwrap.dedent("""\
            @echo off
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
            echo Configuring environment variables
            """.format(filename=filename, vars=" ".join(self._values.keys())))
        result = [capture]
        for k, v in self._values.items():
            if v.action == EnvironmentItem.CLEAN:
                result.append('set {}='.format(k))
            elif v.action == EnvironmentItem.DEFINE:
                value = v.separator.join(v.value)
                result.append('set {}={}'.format(k, value))
            elif v.action == EnvironmentItem.APPEND:
                value = v.separator.join(["%{}%".format(k)]+v.value)
                result.append('set {}={}'.format(k, value))
            else:
                assert v.action == EnvironmentItem.PREPEND
                value = v.separator.join(v.value+["%{}%".format(k)])
                result.append('set {}={}'.format(k, value))

        content = "\n".join(result)
        save(filename, content)

    def save_sh(self, filename):
        capture = textwrap.dedent(r"""\
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
            if v.action == EnvironmentItem.CLEAN:
                result.append('unset {}'.format(k))
            elif v.action == EnvironmentItem.DEFINE:
                value = v.separator.join(v.value)
                result.append('export {}="{}"'.format(k, value))
            elif v.action == EnvironmentItem.APPEND:
                value = v.separator.join(["${k}".format(k=k)]+v.value)
                result.append('export {}="{}"'.format(k, value))
            else:
                assert v.action == EnvironmentItem.PREPEND
                value = v.separator.join(v.value+["${k}".format(k=k)])
                result.append('export {}="{}"'.format(k, value))

        content = "\n".join(result)
        save(filename, content)

    def copy(self):
        result = Environment()
        for k, v in self._values.items():
            result._values[k] = v.copy()
        return result

    def compose(self, other):
        """
        :type other: Environment
        """
        result = self.copy()
        for k, v in other._values.items():
            existing = result._values.get(k)
            if existing is None:
                result._values[k] = v.copy()
            else:
                existing.update(v.copy())
        return result
