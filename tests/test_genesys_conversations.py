"""GenesysConversations.enable: the config source-genesys-conversations 0.0.5 reads."""
import unittest
from unittest import mock

from airbyte_client.helper import GenesysConversations


def enable_args(*args, **kwargs):
    conn = GenesysConversations.__new__(GenesysConversations)  # no Airbyte needed: connect() is mocked
    with mock.patch.object(GenesysConversations, 'connect', return_value=(None, None)) as connect:
        conn.enable('ws', 'customer', 1, *args, **kwargs)
    return connect.call_args[0]


class GenesysConversationsEnableTest(unittest.TestCase):
    def test_region_becomes_both_hosts_and_calls_are_off_by_default(self):
        _, _, _, config, streams = enable_args(' EUW2.pure.cloud ', 'id', 'secret', start_date='2026-10-01T00:00:00Z')
        self.assertEqual(config, {
            'region': 'euw2.pure.cloud',
            'base_url': 'https://api.euw2.pure.cloud',
            'auth_url': 'https://login.euw2.pure.cloud/oauth/token',
            'client_id': 'id', 'client_secret': 'secret',
            'start_date': '2026-10-01',
            'include_voice_calls': False,
        })
        self.assertEqual(set(streams), {'conversations', 'emailconversations'})
        self.assertTrue(all(s == {'syncMode': 'incremental', 'destinationSyncMode': 'append'}
                            for s in streams.values()))

    def test_calls_can_be_turned_on(self):
        config = enable_args('mypurecloud.com', 'id', 'secret', include_voice_calls=True)[3]
        self.assertIs(config['include_voice_calls'], True)

    def test_optional_settings_pass_only_when_given(self):
        config = enable_args('mypurecloud.com', 'id', 'secret')[3]
        self.assertNotIn('batch_size', config)
        self.assertNotIn('concurrency', config)
        config = enable_args('mypurecloud.com', 'id', 'secret', batch_size=100, concurrency=4)[3]
        self.assertEqual((config['batch_size'], config['concurrency']), (100, 4))

    def test_unknown_setting_is_refused(self):
        with self.assertRaises(ValueError):
            enable_args('mypurecloud.com', 'id', 'secret', gemini_api_key='x')

    def test_default_start_is_30_days_back(self):
        config = enable_args('mypurecloud.com', 'id', 'secret')[3]
        self.assertRegex(config['start_date'], r'^\d{4}-\d{2}-\d{2}$')

    def test_name_is_the_genesys_partition(self):
        conn = GenesysConversations.__new__(GenesysConversations)
        with mock.patch('airbyte_client.helper.AnecdoteConnection.__init__') as base:
            GenesysConversations.__init__(conn, None, 'def', 'dest', 'bucket', 'region', {})
        self.assertEqual(base.call_args[0][1], 'Genesys')


if __name__ == '__main__':
    unittest.main()
