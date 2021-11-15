# coding=utf-8

import os
import unittest
import mock

from conans.util import env_reader


class ToolsEnvTest(unittest.TestCase):
    def test_environment_set_variables(self):
        with mock.patch.dict('os.environ', {}), env_reader.environment_set({'env_var1': 'value',
                                                                        'env_var2': 'value2'}):
            self.assertEqual(os.environ['env_var1'], 'value')
            self.assertEqual(os.environ['env_var2'], 'value2')

    def test_environment_set_variables_without_values(self):
        with mock.patch.dict('os.environ', {'env_var1': 'value',
                                            'env_var2': 'value2'}), env_reader.environment_set({}):
            self.assertEqual(os.environ['env_var1'], 'value')
            self.assertEqual(os.environ['env_var2'], 'value2')

    def test_environment_set_overwriting(self):
        with mock.patch.dict('os.environ', {'env_var1': 'value'}),\
             env_reader.environment_set({'env_var1': 'new_value'}):
            self.assertEqual(os.environ['env_var1'], 'new_value')

    def test_environment_set_unsetting_some_variables(self):
        with mock.patch.dict('os.environ', {'env_var1': 'value'}),\
             env_reader.environment_set({'env_var1': None, 'env_var2': 'value2'}):
            self.assertNotIn('env_var1', os.environ)
            self.assertEqual(os.environ['env_var2'], 'value2')

    def test_environment_set_unsetting_all_variables(self):
        with mock.patch.dict('os.environ',
                             {'env_var1': 'value',
                              'env_var2': 'value2'}),\
             env_reader.environment_set({'env_var1': None}):
            self.assertNotIn('env_var1', os.environ)

    def test_environment_set_unsetting_non_existing_variables(self):
        with mock.patch.dict('os.environ',
                             {'env_var2': 'value2'}),\
             env_reader.environment_set({'env_var1': None}):
            self.assertNotIn('env_var1', os.environ)
