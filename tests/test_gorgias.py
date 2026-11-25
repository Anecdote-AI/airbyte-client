"""Gorgias.enable: the `credentials` object source-gorgias 0.2.0 reads."""
import unittest
from unittest import mock

from airbyte_client.helper import Gorgias


def config_of(*args, **kwargs):
    conn = Gorgias.__new__(Gorgias)  # no Airbyte needed: connect() is mocked
    with mock.patch.object(Gorgias, 'connect', return_value=(None, None)) as connect:
        conn.enable('ws', 'customer', 1, *args, **kwargs)
    return connect.call_args[0][3]


class GorgiasEnableTest(unittest.TestCase):
    def test_the_sign_ins_token_is_an_oauth_access_token_with_its_refresh_pair(self):
        config = config_of('access', 'acme', start_date='2026-11-01', refresh_token='refresh',
                           client_id='app-id', client_secret='app-secret')
        self.assertEqual(config, {
            'credentials': {'credentials': 'oauth2.0', 'access_token': 'access', 'refresh_token': 'refresh',
                            'client_id': 'app-id', 'client_secret': 'app-secret'},
            'subdomain': 'acme', 'start_date': '2026-11-01',
        })
        self.assertNotIn('api_key', config)

    def test_without_the_refresh_pair_only_the_access_token_is_sent(self):
        config = config_of('access', 'acme', start_date='2026-11-01', client_id='', client_secret=None)
        self.assertEqual(config['credentials'], {'credentials': 'oauth2.0', 'access_token': 'access'})

    def test_with_a_username_it_is_a_private_apps_api_token(self):
        config = config_of('token', 'acme', username='me@acme.com', refresh_token='ignored')
        self.assertEqual(config['credentials'], {'credentials': 'api_token', 'api_token': 'token',
                                                 'username': 'me@acme.com'})
        self.assertEqual(config['start_date'], '2022-01-01')


if __name__ == '__main__':
    unittest.main()
