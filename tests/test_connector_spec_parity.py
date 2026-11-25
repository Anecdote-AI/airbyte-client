"""Optional connector settings added for spec parity with anecdote-sources develop (2026-11-25).

Each one reaches the Airbyte source config only when given, so the connector's own spec default
applies otherwise (a null would override it). False and 0 are meaningful values and must pass.
"""
import unittest
from unittest import mock

from airbyte_client.helper import (
    AppStoreRSS, Discord, GenesysAudio, GooglePlayScraper, IntercomThread, SprinklrCases, SprinklrMentions,
    Tiktok, TrustpilotScraper, TwitterMentions, ZendeskConversations,
)


def config_of(cls, *args, **kwargs):
    conn = cls.__new__(cls)  # no Airbyte needed: connect() is mocked
    with mock.patch.object(cls, 'connect', return_value=(None, None)) as connect:
        conn.enable('ws', 'customer', 1, *args, **kwargs)
    return connect.call_args[0][3]


# (class, positional args, new settings with a sample value each)
CASES = [
    (AppStoreRSS, ('app', '123'), {'lookback_days': 0, 'empty_feed_retries': 1}),
    (GooglePlayScraper, ('com.app',), {'lookback_days': 0}),
    (Discord, (['1'], 'bot-token'), {'lookback_days': 3}),
    (IntercomThread, ('token',), {'batch_size': 50}),
    (Tiktok, ('apify', ['@p']), {'collect_comments': False}),
    (TrustpilotScraper, ('apify', 'example.com'), {'reply_lookback_days': 0}),
    (TwitterMentions, ('bearer', 'q'), {'max_tweets_per_request': 100, 'max_lookback_days': 30}),
    (ZendeskConversations, ('sub', {'credentials': 'api_token'}), {
        'ticket_sync_mode': 'incremental_export', 'max_rate_limit_share': 0.5,
        'fallback_rate_limit_per_minute': 100, 'comments_concurrency': 2,
        'archived_backfill': False, 'head_refresh_minutes': 0, 'webhook': 'https://example.com/hook'}),
    (GenesysAudio, ('mypurecloud.com', 'id', 'secret', 'gemini'), {
        'transcription_model': 'gemini-x', 'settle_minutes': 0, 'max_wait_hours': 12,
        'transcode_wait_seconds': 60, 'skip_unrecorded_conversations': False, 'bulk_lookups': True,
        'prompt_profile_yaml': 'name: x'}),
    (SprinklrCases, ('prod2', {'credentials': 'oauth2.0'}), {
        'include_names': False, 'case_time_field': 'createdTime', 'lookback_minutes': 0, 'slice_hours': 12,
        'page_size': 50, 'message_batch_size': 10, 'max_messages_per_case': 100,
        'requests_per_second': 2, 'api_host': 'api3.sprinklr.com', 'token_request_style': 'query'}),
    (SprinklrMentions, ('prod2', {'credentials': 'oauth2.0'}), {
        'mention_slice_hours': 3, 'mention_lookback_hours': 0, 'listening_rows': 50, 'requests_per_second': 2}),
]


class SpecParityTest(unittest.TestCase):
    def test_unset_settings_are_left_out(self):
        for cls, args, settings in CASES:
            with self.subTest(cls=cls.__name__):
                config = config_of(cls, *args)
                self.assertFalse(set(settings) & set(config), f'{cls.__name__} sent unset settings')

    def test_given_settings_reach_the_config_including_false_and_zero(self):
        for cls, args, settings in CASES:
            with self.subTest(cls=cls.__name__):
                config = config_of(cls, *args, **settings)
                self.assertEqual({k: config.get(k, '<missing>') for k in settings}, settings)

    def test_sprinklr_rejects_unknown_and_other_stream_settings(self):
        with self.assertRaises(ValueError):
            config_of(SprinklrCases, 'prod2', {}, listening_rows=50)        # a mentions-only setting
        with self.assertRaises(ValueError):
            config_of(SprinklrMentions, 'prod2', {}, include_names=False)   # a cases-only setting
        with self.assertRaises(ValueError):
            config_of(SprinklrCases, 'prod2', {}, not_a_setting=1)


if __name__ == '__main__':
    unittest.main()
