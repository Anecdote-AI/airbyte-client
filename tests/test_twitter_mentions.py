"""TwitterMentions.enable: the optional streamer/endpoint params reach the source config only when given."""
import unittest
from unittest import mock

from airbyte_client.helper import TwitterMentions


def enable(**kwargs):
    conn = TwitterMentions.__new__(TwitterMentions)  # no Airbyte needed: connect() is mocked
    with mock.patch.object(TwitterMentions, 'connect', return_value=(None, None)) as connect:
        conn.enable('ws', 'customer', 1, 'bearer', 'query', start_date='2026-11-01', **kwargs)
    return connect.call_args[0][3]


class TwitterMentionsEnableTest(unittest.TestCase):
    def test_defaults_unchanged(self):
        self.assertEqual(enable(), {'bearer_token': 'bearer', 'search_query': 'query',
                                    'start_date': '2026-11-01', 'timeout_milliseconds': 3000})

    def test_streamer_and_endpoint(self):
        cfg = enable(streamer_api_key='psk', streamer_api_url='http://streamer/api/tokens/next', search_endpoint='all')
        self.assertEqual(cfg['streamer_api_key'], 'psk')
        self.assertEqual(cfg['streamer_api_url'], 'http://streamer/api/tokens/next')
        self.assertEqual(cfg['search_endpoint'], 'all')
        self.assertEqual(cfg['bearer_token'], 'bearer')


if __name__ == '__main__':
    unittest.main()
