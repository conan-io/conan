from conans.errors import ConanException
from conans.model.config_dict import ConfigDict
from conans.model.config_dict import bad_value_msg, undefined_field


class Settings(ConfigDict):
    def __init__(self, definition=None, name="settings", parent_value=None):
        super(Settings, self).__init__(definition or {}, name, parent_value)

    def constraint(self, constraint_def):
        """ allows to restrict a given Settings object with the input of another Settings object
        1. The other Settings object MUST be exclusively a subset of the former.
           No additions allowed
        2. If the other defines {"compiler": None} means to keep the full specification
        """
        if isinstance(constraint_def, (list, tuple, set)):
            constraint_def = {str(k): None for k in constraint_def or []}
        else:
            constraint_def = {str(k): v for k, v in constraint_def.items()}

        fields_to_remove = []
        for field, config_item in self._data.items():
            if field not in constraint_def:
                fields_to_remove.append(field)
                continue

            other_field_def = constraint_def[field]
            if other_field_def is None:  # Means leave it as is
                continue

            values_to_remove = []
            for value in config_item.values_range:  # value = "Visual Studio"
                if value not in other_field_def:
                    values_to_remove.append(value)
                else:  # recursion
                    if (not config_item.is_final and isinstance(other_field_def, dict) and
                        other_field_def[value] is not None):
                        config_item[value].constraint(other_field_def[value])

            # Sanity check of input constraint values
            for value in other_field_def:
                if value not in config_item.values_range:
                    raise ConanException(bad_value_msg(field, value, config_item.values_range))

            config_item.remove(values_to_remove)

        # Sanity check for input constraint wrong fields
        for field in constraint_def:
            if field not in self._data:
                raise ConanException(undefined_field(self._name, field, self.fields))

        # remove settings not defined in the constraint
        self.remove(fields_to_remove)
