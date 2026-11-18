"""SprinklrCases / SprinklrMentions: what reaches the Airbyte source config and which stream is synced."""
import unittest
from unittest import mock

from airbyte_client.helper import AnecdoteConnection, SprinklrCases, SprinklrMentions

CREDENTIALS = {'credentials': 'oauth2.0', 'api_key': 'k', 'api_secret': 's', 'access_token': 'a', 'refresh_token': 'r'}


def enable(cls, **kwargs):
    conn = cls.__new__(cls)  # no Airbyte needed: connect() is mocked
    with mock.patch.object(cls, 'connect', return_value=(None, None)) as connect:
        conn.enable('ws', 'customer', 7, 'prod2', CREDENTIALS, **kwargs)
    return connect.call_args[0][3], connect.call_args[0][4]


class SprinklrEnableTest(unittest.TestCase):
    def test_cases_minimal(self):
        config, streams = enable(SprinklrCases, start_date='2026-11-01')
        self.assertEqual(config, {'environment': 'prod2', 'credentials': CREDENTIALS,
                                  'start_date': '2026-11-01', 'update_database': False})
        self.assertEqual(streams, {'cases': {'syncMode': 'incremental', 'destinationSyncMode': 'append'}})

    def test_cases_default_start_date_and_optional_fields(self):
        config, _ = enable(SprinklrCases, client_id=777, include_messages=False, requests_per_hour='500')
        self.assertRegex(config['start_date'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(config['client_id'], '777')
        self.assertIs(config['include_messages'], False)
        self.assertEqual(config['requests_per_hour'], 500)

    def test_database_fields_only_with_update_database(self):
        config, _ = enable(SprinklrCases, update_database=True, source_id=5, db_host='h', db_port='5432',
                           db_name='n', db_user='u', db_password='p')
        self.assertEqual({k: config[k] for k in ('update_database', 'source_id', 'db_host', 'db_port',
                                                 'db_name', 'db_user', 'db_password')},
                         {'update_database': True, 'source_id': 5, 'db_host': 'h', 'db_port': '5432',
                          'db_name': 'n', 'db_user': 'u', 'db_password': 'p'})

    def test_mentions_stream_and_request(self):
        config, streams = enable(SprinklrMentions, listening_request='{"timeField": "SN_CREATED_TIME"}')
        self.assertEqual(config['listening_request'], '{"timeField": "SN_CREATED_TIME"}')
        self.assertEqual(list(streams), ['mentions'])
        self.assertNotIn('include_messages', config)

    def test_names_give_the_s3_partitions_the_pipeline_expects(self):
        slug = AnecdoteConnection._AnecdoteConnection__transform_name
        self.assertEqual(slug(SprinklrCases.CONNECTION_NAME), 'sprinklr-cases')
        self.assertEqual(slug(SprinklrMentions.CONNECTION_NAME), 'sprinklr-mentions')


if __name__ == '__main__':
    unittest.main()
