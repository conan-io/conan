import os
import mock

import conan.test.utils.env


class TestToolsEnv:
    def test_environment_update_variables(self):
        with mock.patch.dict('os.environ', {}), conan.test.utils.env.environment_update({'env_var1': 'value',
                                                                        'env_var2': 'value2'}):
            assert os.environ['env_var1'] == 'value'
            assert os.environ['env_var2'] == 'value2'

    def test_environment_update_variables_without_values(self):
        with mock.patch.dict('os.environ', {'env_var1': 'value',
                                            'env_var2': 'value2'}), conan.test.utils.env.environment_update({}):
            assert os.environ['env_var1'] == 'value'
            assert os.environ['env_var2'] == 'value2'

    def test_environment_update_overwriting(self):
        with mock.patch.dict('os.environ', {'env_var1': 'value'}),\
             conan.test.utils.env.environment_update({'env_var1': 'new_value'}):
            assert os.environ['env_var1'] == 'new_value'

    def test_environment_update_unsetting_some_variables(self):
        with mock.patch.dict('os.environ', {'env_var1': 'value'}),\
             conan.test.utils.env.environment_update({'env_var1': None, 'env_var2': 'value2'}):
            assert 'env_var1' not in os.environ
            assert os.environ['env_var2'] == 'value2'

    def test_environment_update_unsetting_all_variables(self):
        with mock.patch.dict('os.environ',
                             {'env_var1': 'value',
                              'env_var2': 'value2'}),\
             conan.test.utils.env.environment_update({'env_var1': None}):
            assert 'env_var1' not in os.environ

    def test_environment_update_unsetting_non_existing_variables(self):
        with mock.patch.dict('os.environ',
                             {'env_var2': 'value2'}),\
             conan.test.utils.env.environment_update({'env_var1': None}):
            assert 'env_var1' not in os.environ
