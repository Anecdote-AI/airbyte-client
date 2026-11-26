"""Compatibility tests for the Airbyte 1.6 -> 1.8 changes.

No server needed: `requests.request` is replaced by a fake that records each call and answers from a script.
Run: python -m pytest tests  (or: python -m unittest discover tests)
"""
import json
import unittest
from unittest import mock

import requests

from airbyte_client.client import Client, DEFAULT_ORGANIZATION_ID
from airbyte_client.helper import Helper as AirbyteHelper

HOST = 'airbyte.test'
BASE = f'http://{HOST}:8000/api/v1/'
SLACK = 'https://hooks.slack.test/abc'


def resp(status, body=None, text=None):
    r = requests.Response()
    r.status_code = status
    r._content = (text if text is not None else json.dumps(body if body is not None else {})).encode()
    r.encoding = 'utf-8'
    return r


def ws(i):
    return {'workspaceId': f'ws-{i}', 'name': f'name-{i}', 'slug': f'slug-{i}'}


class FakeServer:
    """Answers `requests.request` from a list of handlers keyed by path (after /api/v1/)."""

    def __init__(self, routes):
        self.routes = routes  # path -> callable(body) -> Response, or a list of Responses (consumed in order)
        self.calls = []

    def __call__(self, method, url, headers=None, json=None, timeout=None):
        assert url.startswith(BASE), url
        path = url[len(BASE):]
        self.calls.append((path, json))
        route = self.routes.get(path)
        if route is None:
            return resp(404, {'message': 'Object not found.'})
        if callable(route):
            return route(json)
        return route.pop(0)

    def paths(self):
        return [p for p, _ in self.calls]


def client():
    return Client(False, HOST, 8000, 'token')


class Base(unittest.TestCase):
    def serve(self, routes):
        server = FakeServer(routes)
        patcher = mock.patch('requests.request', server)
        patcher.start()
        self.addCleanup(patcher.stop)
        return server


OLD_SLACK_ITEM = {'notificationType': ['slack'], 'slackConfiguration': {'webhook': SLACK}}
CUSTOMERIO_KEYS = ['sendOnSyncDisabled', 'sendOnSyncDisabledWarning', 'sendOnConnectionUpdate',
                   'sendOnConnectionUpdateActionRequired']


class WorkspaceNotificationTests(Base):
    def test_create_with_webhook_sends_the_same_body_as_before(self):
        server = self.serve({'workspaces/create': lambda b: resp(200, {'workspaceId': 'new'})})
        r = client().workspaces().create('proj', 'a@b.c', SLACK)
        self.assertTrue(r.ok)
        path, body = server.calls[0]
        self.assertEqual(path, 'workspaces/create')
        ns = body['notificationSettings']
        self.assertEqual(ns['sendOnSuccess'], OLD_SLACK_ITEM)
        self.assertEqual(ns['sendOnFailure'], OLD_SLACK_ITEM)
        for k in CUSTOMERIO_KEYS:
            self.assertEqual(ns[k], {'notificationType': ['customerio']})
        self.assertEqual(body['name'], 'proj')
        self.assertEqual(body['email'], 'a@b.c')
        self.assertEqual(body['organizationId'], DEFAULT_ORGANIZATION_ID)
        self.assertEqual(body['defaultGeography'], 'auto')

    def test_create_without_webhook_sends_no_slack_item(self):
        for webhook in ('', None):
            server = self.serve({'workspaces/create': lambda b: resp(200, {})})
            client().workspaces().create('proj', 'a@b.c', webhook)
            ns = server.calls[0][1]['notificationSettings']
            self.assertEqual(ns['sendOnSuccess'], {'notificationType': []})
            self.assertEqual(ns['sendOnFailure'], {'notificationType': []})
            for k in CUSTOMERIO_KEYS:
                self.assertEqual(ns[k], {'notificationType': ['customerio']})

    def test_create_positional_and_default_args_still_work(self):
        server = self.serve({'workspaces/create': lambda b: resp(200, {})})
        client().workspaces().create('proj')
        self.assertIsNone(server.calls[0][1]['email'])

    def test_update_uses_the_same_rules(self):
        server = self.serve({'workspaces/update': lambda b: resp(200, {})})
        client().workspaces().update('ws-1', 'a@b.c', SLACK)
        client().workspaces().update('ws-1', 'a@b.c', '')
        self.assertEqual(server.calls[0][1]['notificationSettings']['sendOnSuccess'], OLD_SLACK_ITEM)
        self.assertEqual(server.calls[1][1]['notificationSettings']['sendOnSuccess'], {'notificationType': []})
        self.assertEqual(server.calls[0][1]['workspaceId'], 'ws-1')


class WorkspaceListTests(Base):
    def test_old_endpoint_present_returns_it_untouched(self):
        payload = {'workspaces': [ws(1), ws(2)]}
        server = self.serve({'workspaces/list': lambda b: resp(200, payload)})
        r = client().workspaces().list()
        self.assertEqual(server.paths(), ['workspaces/list'])
        self.assertEqual(r.json(), payload)

    def test_old_endpoint_error_other_than_404_is_returned_without_fallback(self):
        for status in (500, 524, 401):
            server = self.serve({'workspaces/list': lambda b, s=status: resp(s, {})})
            r = client().workspaces().list()
            self.assertEqual(r.status_code, status)
            self.assertEqual(server.paths(), ['workspaces/list'])

    def test_network_error_is_still_524_without_fallback(self):
        with mock.patch('requests.request', side_effect=requests.ConnectionError('down')) as m:
            r = client().workspaces().list()
        self.assertEqual(r.status_code, 524)
        self.assertEqual(m.call_count, 1)

    def test_404_falls_back_to_paged_list_by_organization_id(self):
        all_ws = [ws(i) for i in range(503)]

        def page(body):
            self.assertEqual(body['organizationId'], DEFAULT_ORGANIZATION_ID)
            p = body['pagination']
            return resp(200, {'workspaces': all_ws[p['rowOffset']:p['rowOffset'] + p['pageSize']]})

        server = self.serve({'workspaces/list_by_organization_id': page})
        r = client().workspaces().list()
        self.assertTrue(r.ok)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'workspaces': all_ws})
        self.assertEqual(server.paths(), ['workspaces/list'] + ['workspaces/list_by_organization_id'] * 2)
        self.assertEqual([b['pagination'] for _, b in server.calls[1:]],
                         [{'pageSize': 500, 'rowOffset': 0}, {'pageSize': 500, 'rowOffset': 500}])

    def test_exact_multiple_of_page_size_ends_on_the_empty_page(self):
        all_ws = [ws(i) for i in range(4)]
        server = self.serve({'workspaces/list_by_organization_id': lambda b: resp(200, {
            'workspaces': all_ws[b['pagination']['rowOffset']:][:b['pagination']['pageSize']]})})
        r = client().workspaces().list(page_size=2)
        self.assertEqual(len(r.json()['workspaces']), 4)
        self.assertEqual(len(server.calls), 1 + 3)

    def test_server_ignoring_pagination_does_not_loop(self):
        all_ws = [ws(i) for i in range(3)]
        server = self.serve({'workspaces/list_by_organization_id': lambda b: resp(200, {'workspaces': all_ws})})
        r = client().workspaces().list(page_size=3)
        self.assertEqual(r.json(), {'workspaces': all_ws})
        self.assertEqual(len(server.calls), 1 + 2)

    def test_failed_page_returns_the_failure(self):
        server = self.serve({'workspaces/list_by_organization_id': [resp(200, {'workspaces': [ws(1), ws(2)]}),
                                                                    resp(500, {'message': 'boom'})]})
        r = client().workspaces().list(page_size=2)
        self.assertFalse(r.ok)
        self.assertEqual(r.status_code, 500)

    def test_empty_install(self):
        self.serve({'workspaces/list_by_organization_id': lambda b: resp(200, {'workspaces': []})})
        self.assertEqual(client().workspaces().list().json(), {'workspaces': []})


class HelperWorkspaceTests(Base):
    """VoC project create/delete go through these helpers."""

    def routes_18(self, existing):
        return {'workspaces/list_by_organization_id': lambda b: resp(200, {'workspaces': existing}),
                'workspaces/create': lambda b: resp(200, {'workspaceId': 'new', 'name': b['name']}),
                'workspaces/delete': lambda b: resp(204, text=''),
                'connections/list': lambda b: resp(200, {'connections': []}),
                'destinations/list': lambda b: resp(200, {'destinations': []}),
                'sources/list': lambda b: resp(200, {'sources': []})}

    def test_create_safe_on_1_8(self):
        server = self.serve(self.routes_18([ws(1)]))
        r, err = AirbyteHelper(client()).workspace_create_safe('fresh', 'a@b.c', '')
        self.assertIsNone(err)
        self.assertEqual(r.json()['workspaceId'], 'new')
        self.assertEqual(server.calls[-1][1]['notificationSettings']['sendOnSuccess'], {'notificationType': []})

    def test_create_safe_still_detects_duplicates_by_name_and_slug(self):
        for dup in ('name-1', 'slug-1'):
            self.serve(self.routes_18([ws(1)]))
            _, err = AirbyteHelper(client()).workspace_create_safe(dup)
            self.assertEqual(err['error_code'], 409)

    def test_delete_safe_on_1_8(self):
        server = self.serve(self.routes_18([ws(1)]))
        _, err = AirbyteHelper(client()).workspace_delete_safe('ws-1')
        self.assertIsNone(err)
        self.assertEqual(server.paths()[-1], 'workspaces/delete')

    def test_delete_safe_unknown_workspace_is_404(self):
        self.serve(self.routes_18([ws(1)]))
        _, err = AirbyteHelper(client()).workspace_delete_safe('ws-x')
        self.assertEqual(err['error_code'], 404)

    def test_create_safe_on_1_6_unchanged(self):
        server = self.serve({'workspaces/list': lambda b: resp(200, {'workspaces': [ws(1)]}),
                             'workspaces/create': lambda b: resp(200, {'workspaceId': 'new'})})
        _, err = AirbyteHelper(client()).workspace_create_safe('fresh', 'a@b.c', SLACK)
        self.assertIsNone(err)
        self.assertEqual(server.paths(), ['workspaces/list', 'workspaces/create'])


NEEDS_WS = 'Internal Server Error: getWorkspaceId(...) must not be null'


class DefinitionUpdateTests(Base):
    def kinds(self):
        return [('source_definitions', lambda c: c.source_definitions(), 'sourceDefinitionId'),
                ('destination_definitions', lambda c: c.destination_definitions(), 'destinationDefinitionId')]

    def test_success_without_workspace_is_one_unchanged_call(self):
        for res, get, key in self.kinds():
            server = self.serve({f'{res}/update': lambda b: resp(200, b)})
            r = get(client()).update('def-1', '1.2.3')
            self.assertTrue(r.ok)
            self.assertEqual(server.calls, [(f'{res}/update', {key: 'def-1', 'dockerImageTag': '1.2.3'})])

    def test_resource_requirements_positional_still_works(self):
        rr = {'default': {'cpu_limit': '1'}}
        server = self.serve({'source_definitions/update': lambda b: resp(200, b)})
        client().source_definitions().update('def-1', '1.2.3', rr)
        self.assertEqual(server.calls[0][1]['resourceRequirements'], rr)
        self.assertNotIn('workspaceId', server.calls[0][1])

    def test_1_8_missing_workspace_500_retries_with_a_workspace(self):
        for res, get, key in self.kinds():
            server = self.serve({
                f'{res}/update': lambda b: resp(200, b) if 'workspaceId' in b else resp(500, {'message': NEEDS_WS}),
                'workspaces/list_by_organization_id': lambda b: resp(200, {'workspaces': [ws(7), ws(8)]})})
            r = get(client()).update('def-1', '1.2.3')
            self.assertTrue(r.ok)
            self.assertEqual(server.paths(), [f'{res}/update', 'workspaces/list', 'workspaces/list_by_organization_id',
                                              f'{res}/update'])
            self.assertEqual(server.calls[-1][1], {key: 'def-1', 'dockerImageTag': '1.2.3', 'workspaceId': 'ws-7'})

    def test_other_500_is_not_retried(self):
        server = self.serve({'source_definitions/update': lambda b: resp(500, {'message': 'something else'})})
        r = client().source_definitions().update('def-1', '1.2.3')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(len(server.calls), 1)

    def test_1_6_hang_is_still_one_call(self):
        with mock.patch('requests.request', side_effect=requests.Timeout('hang')) as m:
            r = client().source_definitions().update('def-1', '1.2.3')
        self.assertEqual(r.status_code, 524)
        self.assertEqual(m.call_count, 1)

    def test_no_workspace_found_returns_the_original_500(self):
        self.serve({'source_definitions/update': lambda b: resp(500, {'message': NEEDS_WS}),
                    'workspaces/list_by_organization_id': lambda b: resp(200, {'workspaces': []})})
        r = client().source_definitions().update('def-1', '1.2.3')
        self.assertEqual(r.status_code, 500)

    def test_explicit_workspace_is_sent_once(self):
        server = self.serve({'source_definitions/update': lambda b: resp(200, b)})
        client().source_definitions().update('def-1', '1.2.3', workspace_id='ws-1')
        self.assertEqual(server.calls, [('source_definitions/update',
                                         {'sourceDefinitionId': 'def-1', 'dockerImageTag': '1.2.3',
                                          'workspaceId': 'ws-1'})])

    def test_update_custom_sends_the_flat_body(self):
        for res, get, key in self.kinds():
            server = self.serve({f'{res}/update': lambda b: resp(200, b)})
            get(client()).update_custom('ws-1', 'def-1', '1.2.3')
            self.assertEqual(server.calls, [(f'{res}/update',
                                             {key: 'def-1', 'dockerImageTag': '1.2.3', 'workspaceId': 'ws-1'})])

    def test_sibling_client_keeps_host_token_and_timeout(self):
        c = Client(True, 'h.test', 443, 'tok', timeout_ms=5000)
        defs = c.source_definitions()
        sib = defs._sibling('workspaces/')
        self.assertEqual(sib.base_url, 'https://h.test:443/api/v1/workspaces/')
        self.assertEqual(sib.headers, {'Authorization': 'Bearer tok'})
        # Same timeout as the client making the update (the resource factories already reset it to the default).
        self.assertEqual(sib.timeout_ms, defs.airbyte_client.timeout_ms)


if __name__ == '__main__':
    unittest.main()


def airbyte_18_actor_list(items, id_field):
    """Fake 1.8 `sources/list` / `destinations/list`: cursor paged, 20 per page when no pageSize is sent."""
    key = 'sources' if id_field == 'sourceId' else 'destinations'

    def handler(body):
        size = body.get('pageSize', 20)
        start = 0
        if body.get('cursor'):
            start = [x[id_field] for x in items].index(body['cursor']) + 1
        return resp(200, {key: items[start:start + size], 'numConnections': len(items), 'pageSize': size})
    return handler


def src(i):
    return {'sourceId': f'src-{i:03d}', 'name': f'source-{i}'}


def dst(i):
    return {'destinationId': f'dst-{i:03d}', 'name': f'destination-{i}'}


class ActorListPagingTests(Base):
    """Airbyte 1.8 caps sources/list and destinations/list at 20 unless pageSize is sent."""

    def test_sources_list_returns_more_than_20(self):
        items = [src(i) for i in range(45)]
        server = self.serve({'sources/list': airbyte_18_actor_list(items, 'sourceId')})
        r = client().sources().list('ws-1')
        self.assertTrue(r.ok)
        self.assertEqual(r.json(), {'sources': items})
        self.assertEqual(server.calls, [('sources/list', {'workspaceId': 'ws-1', 'pageSize': 100})])

    def test_sources_list_follows_the_cursor(self):
        items = [src(i) for i in range(45)]
        server = self.serve({'sources/list': airbyte_18_actor_list(items, 'sourceId')})
        r = client().sources().list('ws-1', page_size=20)
        self.assertEqual(r.json()['sources'], items)
        self.assertEqual([b.get('cursor') for _, b in server.calls], [None, 'src-019', 'src-039'])

    def test_exact_multiple_of_page_size_ends_on_the_empty_page(self):
        items = [src(i) for i in range(40)]
        server = self.serve({'sources/list': airbyte_18_actor_list(items, 'sourceId')})
        self.assertEqual(client().sources().list('ws-1', page_size=20).json()['sources'], items)
        self.assertEqual(len(server.calls), 3)

    def test_server_ignoring_pagination_does_not_loop(self):
        items = [src(i) for i in range(5)]
        server = self.serve({'sources/list': lambda b: resp(200, {'sources': items})})
        self.assertEqual(client().sources().list('ws-1', page_size=5).json(), {'sources': items})
        self.assertEqual(len(server.calls), 2)

    def test_failed_page_returns_the_failure(self):
        self.serve({'sources/list': [resp(200, {'sources': [src(1), src(2)]}), resp(500, {'message': 'boom'})]})
        r = client().sources().list('ws-1', page_size=2)
        self.assertEqual(r.status_code, 500)

    def test_network_error_is_still_524(self):
        with mock.patch('requests.request', side_effect=requests.ConnectionError('down')):
            self.assertEqual(client().sources().list('ws-1').status_code, 524)

    def test_destinations_list_returns_more_than_20(self):
        items = [dst(i) for i in range(25)]
        server = self.serve({'destinations/list': airbyte_18_actor_list(items, 'destinationId')})
        self.assertEqual(client().destinations().list('ws-1').json(), {'destinations': items})
        self.assertEqual(len(server.calls), 1)

    def test_source_delete_safe_finds_a_source_past_the_first_20(self):
        """The VoC Remove path: connection_delete_safe_full -> source_delete_safe used to 404 here."""
        items = [src(i) for i in range(30)]
        server = self.serve({'sources/list': airbyte_18_actor_list(items, 'sourceId'),
                             'connections/list': lambda b: resp(200, {'connections': []}),
                             'sources/delete': lambda b: resp(204, text='')})
        _, err = AirbyteHelper(client()).source_delete_safe('ws-1', 'src-025')
        self.assertIsNone(err)
        self.assertEqual(server.calls[-1], ('sources/delete', {'sourceId': 'src-025'}))

    def test_source_create_safe_sees_a_duplicate_name_past_the_first_20(self):
        items = [src(i) for i in range(30)]
        self.serve({'sources/list': airbyte_18_actor_list(items, 'sourceId')})
        _, err = AirbyteHelper(client()).source_create_safe('ws-1', 'def', 'source-27', {})
        self.assertEqual(err['error_code'], 409)
