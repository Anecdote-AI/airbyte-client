import time
from datetime import datetime, timedelta
from typing import Mapping, Any, List, Optional, Tuple

import requests

from airbyte_client.client import Base, Client


class Helper(Base):
    def workspace_create_safe(self, name: str, email: Optional[str] = None, webhook_url: Optional[str] = None) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.workspaces().list()
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte workspaces'}

        for workspace in response.json()['workspaces']:
            if (workspace['name'] == name) or (workspace['slug'] == name):
                return response, {'error_code': 409, 'error_str': f'Project name {name} already exists'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.workspaces().create(name, email, webhook_url)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to create Airbyte workspace'}

        return response, None

    def workspace_delete_safe(self, workspace_id: str) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.workspaces().list()
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte workspaces'}
        found = False
        for workspace in response.json()['workspaces']:
            if workspace['workspaceId'] == workspace_id:
                found = True
                break
        if not found:
            return response, {'error_code': 404, 'error_str': f'Workspace ID {workspace_id} was not found'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        if len(response.json()['connections']) != 0:
            return response, {'error_code': 424,
                              'error_str': f'Workspace ID {workspace_id} still has active connections, so cannot be deleted'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.destinations().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte destinations'}
        if len(response.json()['destinations']) != 0:
            return response, {'error_code': 424,
                              'error_str': f'Workspace ID {workspace_id} still has active destinations, so cannot be deleted'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.sources().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte sources'}
        if len(response.json()['sources']) != 0:
            return response, {'error_code': 424,
                              'error_str': f'Workspace ID {workspace_id} still has active sources, so cannot be deleted'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.workspaces().delete(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to delete Airbyte workspace'}
        return response, None

    def source_create_safe(
            self, workspace_id: str, source_definition_id: str,
            name: str, connection_configuration: Mapping[str, Any]
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.sources().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte sources'}
        for source in response.json()['sources']:
            if source['name'] == name:
                return response, {'error_code': 409, 'error_str': f'Source name {name} already exists'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        self.airbyte_client.source_definitions().grant_definition(workspace_id, source_definition_id)

        flag = False
        err = None
        for i in range(self.max_retries):
            time.sleep(self.timeout_between_requests_ms / 1000.0)
            response = self.airbyte_client.scheduler().sources_check_connection(
                workspace_id, source_definition_id, connection_configuration)
            if not response.ok:
                err = {'error_code': 500, 'error_str': 'Internal error: unable to check Airbyte source parameters'}
                print(i, err)
                continue
            data = response.json()
            if 'status' not in data:
                print(data)
                err = {'error_code': 500,
                       'error_str': 'Internal error: no status in Airbyte source check connection response. Please, retry later'}
                print(i, err)
                continue
            if data['status'] != 'succeeded':
                print(data)
                err = {'error_code': 400, 'error_str': 'Source has incorrect configuration'}
                print(i, err)
                continue
            flag = True
            err = None
            break

        if not flag:
            return None, err

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.sources().create(
            workspace_id, source_definition_id,
            name, connection_configuration
        )
        if not response.ok:
            return response, {'error_code': 500,
                              'error_str': 'Internal error: unable to create Airbyte source'}
        return response, None

    def source_delete_safe(self, workspace_id: str, source_id: str) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.sources().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte sources'}
        found = False
        for src in response.json()['sources']:
            if src['sourceId'] == source_id:
                found = True
                break
        if not found:
            return response, {'error_code': 404, 'error_str': f'Source ID {source_id} was not found'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        for connection in response.json()['connections']:
            if connection['sourceId'] == source_id:
                return response, {'error_code': 424,
                                  'error_str': f'Source ID {source_id} still is used in active connection, so cannot be deleted'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.sources().delete(source_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to delete Airbyte source'}
        return response, None

    def destination_create_safe(
            self, workspace_id: str, destination_definition_id: str,
            name: str, connection_configuration: Mapping[str, Any]
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.destinations().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte destinations'}
        for destination in response.json()['destinations']:
            if destination['name'] == name:
                return response, {'error_code': 409, 'error_str': f'Destination name {name} already exists'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        self.airbyte_client.destination_definitions().grant_definition(workspace_id, destination_definition_id)

        flag = False
        err = None
        for i in range(self.max_retries):
            time.sleep(self.timeout_between_requests_ms / 1000.0)
            response = self.airbyte_client.scheduler().destinations_check_connection(
                workspace_id, destination_definition_id, connection_configuration)
            if not response.ok:
                err = {'error_code': 500,
                       'error_str': 'Internal error: unable to check Airbyte destination parameters'}
                print(i, err)
                continue
            data = response.json()
            if 'status' not in data:
                print(data)
                err = {'error_code': 500,
                       'error_str': 'Internal error: no status in Airbyte destination check connection response. Please, retry later'}
                print(i, err)
                continue
            if data['status'] != 'succeeded':
                print(data)
                err = {'error_code': 400, 'error_str': 'Destination has incorrect configuration'}
                print(i, err)
                continue
            flag = True
            err = None
            break

        if not flag:
            return None, err

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.destinations().create(
            workspace_id, destination_definition_id,
            name, connection_configuration
        )
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to create Airbyte destination'}
        return response, None

    def destination_delete_safe(self, workspace_id: str, destination_id: str) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.destinations().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte destinations'}
        found = False
        for src in response.json()['destinations']:
            if src['destinationId'] == destination_id:
                found = True
                break
        if not found:
            return response, {'error_code': 404, 'error_str': f'Destination ID {destination_id} was not found'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        for connection in response.json()['connections']:
            if connection['destinationId'] == destination_id:
                return response, {'error_code': 424,
                                  'error_str': f'Destination ID {destination_id} still is used in active connection, so cannot be deleted'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.destinations().delete(destination_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to delete Airbyte destination'}
        return response, None

    def connection_create_safe(
            self, workspace_id: str, name: str, namespace_definition: str, namespace_format: str,
            prefix: str, source_id: str, destination_id: str,
            streams: List[Mapping[str, Any]], status: str, operation_ids: Optional[List[str]] = None,
            schedule: Optional[Mapping[str, Any]] = None, schedule_type: Optional[str] = None,
            schedule_data: Optional[Mapping[str, Any]] = None,
            resource_requirements: Optional[Mapping[str, Any]] = None,
            source_catalog_id: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        for connection in response.json()['connections']:
            if connection['name'] == name:
                return response, {'error_code': 409, 'error_str': f'Connection name {name} already exists'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.connections().create(
            name, namespace_definition, namespace_format,
            prefix, source_id, destination_id,
            streams, status, operation_ids,
            schedule, schedule_type, schedule_data,
            resource_requirements, source_catalog_id
        )
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to create Airbyte connection'}
        return response, None

    def connection_delete_safe(self, workspace_id: str, connection_id: str) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        found = False
        for connection in response.json()['connections']:
            if connection['connectionId'] == connection_id:
                found = True
                break
        if not found:
            return response, {'error_code': 404, 'error_str': f'Connection ID {connection_id} was not found'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.connections().delete(connection_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to delete Airbyte connection'}
        return response, None

    def connection_create_safe_full(
            self, workspace_id: str, name: str, namespace_definition: str, namespace_format: str, prefix: str,
            source_definition_id: str, source_configuration: Mapping[str, Any],
            destination_definition_id: str, destination_configuration: Mapping[str, Any],
            streams_configuration: Mapping[str, Any], status: str, operation_ids: Optional[List[str]] = None,
            schedule: Optional[Mapping[str, Any]] = None, schedule_type: Optional[str] = None,
            schedule_data: Optional[Mapping[str, Any]] = None,
            resource_requirements: Optional[Mapping[str, Any]] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        print("1")
        response, error_map = self.source_create_safe(
            workspace_id, source_definition_id,
            name, source_configuration
        )
        if error_map is not None:
            return response, error_map
        source_id = response.json()['sourceId']
        print("2")
        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response, error_map = self.destination_create_safe(
            workspace_id, destination_definition_id,
            name, destination_configuration)
        if error_map is not None:
            self.source_delete_safe(workspace_id, source_id)
            return response, error_map
        destination_id = response.json()['destinationId']
        print("3")

        streams = []
        source_catalog_id = 'todo'

        flag = False
        err = None
        for i in range(self.max_retries):
            time.sleep(self.timeout_before_schema_discovery_ms / 1000.0)
            response = self.airbyte_client.sources().discover_schema(source_id, disable_cache=False)
            if not response.ok:
                err = {'error_code': 500, 'error_str': 'Internal error: unable to discover Airbyte schema'}
                print(i, err)
                continue
            data = response.json()
            if ('catalog' not in data) or ('streams' not in data['catalog']):
                print(data)
                err = {'error_code': 500,
                       'error_str': 'Internal error: no streams in Airbyte discover schema response. Please, retry later'}
                print(i, err)
                continue

            streams = data['catalog']['streams']
            for s in streams:
                s['config']['selected'] = False

                stream_configuration = streams_configuration.get(s['stream']['name'])
                if stream_configuration is None:
                    continue
                if stream_configuration.get('selectedFields'):
                    s['config']['selectedFields'] = stream_configuration['selectedFields']
                    s['config']['fieldSelectionEnabled'] = True
                s['config']['syncMode'] = stream_configuration['syncMode']
                s['config']['destinationSyncMode'] = stream_configuration['destinationSyncMode']
                s['config']['selected'] = True
            source_catalog_id = response.json()['catalogId']

            flag = True
            err = None
            break

        if not flag:
            self.destination_delete_safe(workspace_id, destination_id)
            self.source_delete_safe(workspace_id, source_id)
            return None, err

        print("4")
        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response, error_map = self.connection_create_safe(
            workspace_id, name, namespace_definition, namespace_format,
            prefix, source_id, destination_id,
            streams, status, operation_ids,
            schedule, schedule_type, schedule_data,
            resource_requirements,
            source_catalog_id
        )
        if error_map is not None:
            self.destination_delete_safe(workspace_id, destination_id)
            self.source_delete_safe(workspace_id, source_id)
            return response, error_map
        print("5")
        return response, None

    def connection_delete_safe_full(self, workspace_id: str, connection_id: str) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.connections().get(connection_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to get Airbyte connection'}
        destination_id = response.json()['destinationId']
        source_id = response.json()['sourceId']

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response, error_map = self.connection_delete_safe(workspace_id, connection_id)
        if error_map is not None:
            return response, error_map

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response, error_map = self.destination_delete_safe(workspace_id, destination_id)
        if error_map is not None:
            return response, error_map

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response, error_map = self.source_delete_safe(workspace_id, source_id)
        if error_map is not None:
            return response, error_map
        return response, None


class AnecdoteConnection(Helper):
    def __init__(
            self, airbyte_client: Client, name: str, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(airbyte_client)

        self.name = name

        self.source_definition_id = source_definition_id
        self.destination_definition_id = destination_definition_id

        self.destination_configuration = {
            's3_bucket_name': s3_bucket_name,
            's3_bucket_path': 'todo',
            's3_bucket_region': s3_bucket_region,
            'format': s3_format,
        }

        if s3_access_key_id is not None:
            self.destination_configuration['access_key_id'] = s3_access_key_id
        if s3_secret_access_key is not None:
            self.destination_configuration['secret_access_key'] = s3_secret_access_key
        if s3_endpoint is not None:
            self.destination_configuration['s3_endpoint'] = s3_endpoint
        if s3_path_format is not None:
            self.destination_configuration['s3_path_format'] = s3_path_format
        if s3_file_name_pattern is not None:
            self.destination_configuration['s3_file_name_pattern'] = s3_file_name_pattern

        self.schedule = schedule

    @staticmethod
    def __transform_name(name: str) -> str:
        return name.lower().replace(' ', '-').replace('\t', '-') \
            .replace('\n', '-').replace('\r', '-').replace('_', '-')

    def connect(
            self, workspace_id: str, customer_name: str, ind: int,
            source_configuration: Mapping[str, Any],
            streams_configuration: Mapping[str, Any]
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        name = self.__transform_name(self.name)
        customer_name = self.__transform_name(customer_name)

        self.destination_configuration['s3_bucket_path'] = \
            'source-name={}/customer-name={}/source-index={}'.format(
                name, customer_name, ind
            )

        response, error_map = self.connection_create_safe_full(
            workspace_id, self.name + ' | ' + str(ind),
            'destination', '${SOURCE_NAMESPACE}', '',
            self.source_definition_id, source_configuration,
            self.destination_definition_id, self.destination_configuration,
            streams_configuration,
            'active',
            schedule=self.schedule
        )
        return response, error_map

    def update_schedule(
            self, workspace_id: str, customer_name: str, ind: int,
            schedule_type: str = 'manual', schedule_data: Optional[Mapping[str, Any]] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        found = False
        connection_id = None
        name = self.name + ' | ' + str(ind)
        for connection in response.json()['connections']:
            if connection['name'] == name:
                found = True
                connection_id = connection['connectionId']
                break
        if not found:
            return response, {'error_code': 404, 'error_str': f'Connection ID {name} was not found'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.connections().update(
            connection_id, schedule_type=schedule_type, schedule_data=schedule_data)
        if not response.ok:
            return response, {'error_code': 500,
                              'error_str': 'Internal error: unable to update Airbyte connections schedule'}
        return response, None

    def run_sync_job(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        found = False
        connection_id = None
        name = self.name + ' | ' + str(ind)
        for connection in response.json()['connections']:
            if connection['name'] == name:
                found = True
                connection_id = connection['connectionId']
                break
        if not found:
            return response, {'error_code': 404, 'error_str': f'Connection name {name} was not found'}

        flag = False
        err = None
        for i in range(self.max_retries):
            time.sleep(self.timeout_between_requests_ms / 1000.0)
            response = self.airbyte_client.connections().sync(connection_id)
            if not response.ok:
                err = {'error_code': 500, 'error_str': 'Internal error: unable to trigger Airbyte connection sync'}
                continue
            flag = True
            err = None
            break

        if not flag:
            return None, err

        return response, None

    def get_last_sync_job_info(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        found = False
        connection_id = None
        name = self.name + ' | ' + str(ind)
        for connection in response.json()['connections']:
            if connection['name'] == name:
                found = True
                connection_id = connection['connectionId']
                break
        if not found:
            return response, {'error_code': 404, 'error_str': f'Connection name {name} was not found'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response = self.airbyte_client.jobs().get_last_replication_job(connection_id)
        if not response.ok:
            return response, {'error_code': 500,
                              'error_str': 'Internal error: unable to get last Airbyte replication job'}
        return response, None

    def disconnect(self, workspace_id: str, ind: int) -> Tuple[
        Optional[requests.Response], Optional[Mapping[str, Any]]]:
        response = self.airbyte_client.connections().list(workspace_id)
        if not response.ok:
            return response, {'error_code': 500, 'error_str': 'Internal error: unable to list Airbyte connections'}
        found = False
        connection_id = None
        name = self.name + ' | ' + str(ind)
        for connection in response.json()['connections']:
            if connection['name'] == self.name + ' | ' + str(ind):
                found = True
                connection_id = connection['connectionId']
                break
        if not found:
            return response, {'error_code': 404, 'error_str': f'Connection name {name} was not found'}

        time.sleep(self.timeout_between_requests_ms / 1000.0)
        response, error_map = self.connection_delete_safe_full(workspace_id, connection_id)
        return response, error_map


class AnecdoteSurveys(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'AnecdoteSurveys', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, project_id: int, admin_psk: str, base_url: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%d')

        source_configuration = {
            'project_id': project_id,
            'admin_psk': admin_psk,
            'base_url': base_url,
            'start_date': start_date,
        }

        streams_configuration = {
            'responses': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'surveys': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)

class ApifyTwitterMentions(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Apify Twitter Mentions', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, apify_token: str, mentions: List[str],
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%d')

        source_configuration = {
            'apify_token': apify_token,
            'mentions': mentions,
            'start_date': start_date,
        }

        streams_configuration = {
            'tweets': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)

class AppStoreAMP(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'App Store AMP', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, app_name: str, app_id: str,
            countries: Optional[Mapping[str, Any]] = None, start_date: Optional[str] = None,
            timeout_milliseconds: Optional[int] = None, max_reviews_per_request: Optional[int] = None,
            proxy_config: Optional[Mapping[str, Any]] = None, country: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if countries is None:
            countries = {'type': 'all'}
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'app_name': app_name,
            'app_id': app_id,
            'countries': countries,
            'start_date': start_date
        }
        if country is not None:
            source_configuration['country'] = country

        if timeout_milliseconds is not None:
            source_configuration['timeout_milliseconds'] = timeout_milliseconds
        if max_reviews_per_request is not None:
            source_configuration['max_reviews_per_request'] = max_reviews_per_request

        if country is not None:
            source_configuration['country'] = country

        if not proxy_config:
            streams_configuration = {
                'reviews': {
                    'syncMode': 'full_refresh',
                    'destinationSyncMode': 'overwrite',
                }
            }
        else:
            streams_configuration = {
                'reviews_proxy': {
                    'syncMode': 'full_refresh',
                    'destinationSyncMode': 'overwrite',
                }
            }
            source_configuration['zyte_api_key'] = proxy_config['zyte_api_key']

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class AppStoreRSS(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'App Store RSS', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, app_name: str, app_id: str,
            countries: Optional[Mapping[str, Any]] = None, start_date: Optional[str] = None,
            timeout_milliseconds: Optional[int] = None,
            proxy_config: Optional[Mapping[str, Any]] = None, country: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if countries is None:
            countries = {'type': 'all'}
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'app_name': app_name,
            'app_id': app_id,
            'countries': countries,
            'start_date': start_date
        }
        if country is not None:
            source_configuration['country'] = country
        if timeout_milliseconds is not None:
            source_configuration['timeout_milliseconds'] = timeout_milliseconds

        if country is not None:
            source_configuration['country'] = country

        if not proxy_config:
            streams_configuration = {
                'reviews': {
                    'syncMode': 'incremental',
                    'destinationSyncMode': 'append',
                }
            }
        else:
            streams_configuration = {
                'reviews_proxy': {
                    'syncMode': 'incremental',
                    'destinationSyncMode': 'append',
                }
            }
            source_configuration['zyte_api_key'] = proxy_config['zyte_api_key']

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class Delighted(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Delighted', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, delighted_api_key: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01T01:00:00Z'

        source_configuration = {
            'api_key': delighted_api_key,
            'since': start_date + 'T01:00:00Z',
        }

        streams_configuration = {
            'survey_responses': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)

class Discord(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Discord', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, channels: List[str], token: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'channels': channels,
            'token': token,
            'start_date': start_date,
        }

        streams_configuration = {
            'messages': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)


    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)

class Freshdesk(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Freshdesk', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, domain: str, api_key: str,
            start_date: Optional[str] = None, requests_per_minute: int = 50
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'domain': domain,
            'start_date': start_date + 'T00:00:00Z',
            'api_key': api_key,
            'requests_per_minute': requests_per_minute
        }

        streams_configuration = {
            'agents': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite'
            },
            'companies': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite'
            },
            'groups': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite'
            },
            'roles': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite'
            },
            'satisfaction_ratings': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append'
            },
            'surveys': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite'
            },
            'tickets': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append'
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class G2Reviews(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'G2 Reviews', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, keywords: List[str], apify_token: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'keywords': keywords,
            'apify_token': apify_token,
            'start_date': start_date,
        }

        streams_configuration = {
            'reviews': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class GoogleMapsReviews(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Google Maps Reviews', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, urls: List[str], apify_token: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'urls': urls,
            'apify_token': apify_token,
            'start_date': start_date,
        }

        streams_configuration = {
            'reviews': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class GooglePlayScraper(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Google Play Scraper', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, app_id: str,
            languages: Optional[Mapping[str, Any]] = None, start_date: Optional[str] = None, country: str = 'US',
            timeout_milliseconds: Optional[int] = None, max_reviews_per_request: Optional[int] = None,
            proxy_config: Optional[Mapping[str, Any]] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if languages is None:
            languages = {'type': 'all'}
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'app_id': app_id,
            'languages': languages,
            'start_date': start_date,
            'country': country
        }
        if timeout_milliseconds is not None:
            source_configuration['timeout_milliseconds'] = timeout_milliseconds
        if max_reviews_per_request is not None:
            source_configuration['max_reviews_per_request'] = max_reviews_per_request

        if not proxy_config:
            streams_configuration = {
                'reviews': {
                    'syncMode': 'incremental',
                    'destinationSyncMode': 'append',
                }
            }
        else:
            streams_configuration = {
                'reviews_proxy': {
                    'syncMode': 'incremental',
                    'destinationSyncMode': 'append',
                }
            }
            source_configuration['zyte_api_key'] = proxy_config['zyte_api_key']
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class Gorgias(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Gorgias', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, api_key: str, subdomain: str,
            start_date: Optional[str] = None,
            timeout_milliseconds: Optional[int] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'api_key': api_key,
            'subdomain': subdomain,
            'start_date': start_date,
        }
        if timeout_milliseconds is not None:
            source_configuration['timeout_milliseconds'] = timeout_milliseconds

        streams_configuration = {
            'messages': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class HubSpot(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'HubSpot', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, access_token: str,
            start_date: Optional[str] = None,
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'
        source_configuration = {
            'start_date': start_date + 'T00:00:00Z',
            'credentials': {
                "credentials_title": "Private App Credentials",
                "access_token": access_token
            }
        }
        streams_configuration = {
            'tickets': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class Intercom(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Intercom', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, access_token: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'access_token': access_token,
            'start_date': start_date + 'T00:00:00Z',
        }

        streams_configuration = {
            'conversation_parts': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'conversations': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'tags': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
            },
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class IntercomThread(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Intercom Thread', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, access_token: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'access_token': access_token,
            'start_date': start_date + 'T00:00:00Z',
        }

        streams_configuration = {
            'conversation_parts': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'conversations': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class Kustomer(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Kustomer', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, api_token: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01T00:00:00Z'

        source_configuration = {
            'api_token': api_token,
            'start_date': start_date + 'T00:00:00Z',
        }

        streams_configuration = {
            'messages': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class Pendo(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Pendo', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, api_key: str
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        source_configuration = {
            'api_key': api_key
        }

        streams_configuration = {
            'report': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class Reddit(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Reddit', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, urls: List[str], apify_token: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'urls': urls,
            'apify_token': apify_token,
            'start_date': start_date,
        }

        streams_configuration = {
            'comments': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class SendBird(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'SendBird', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, application_id: str, token: str,
            start_date: Optional[str] = None,
            timeout_milliseconds: Optional[int] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            sendbird_start_date = datetime.now() - timedelta(days=30)
            start_date = sendbird_start_date.strftime('%Y-%m-%d')

        source_configuration = {
            'application_id': application_id,
            'token': token,
            'start_date': start_date,
        }
        if timeout_milliseconds is not None:
            source_configuration['timeout_milliseconds'] = timeout_milliseconds

        streams_configuration = {
            'messages': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class SteamReviews(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Steam Reviews', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, app_ids: List[str], apify_token: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'app_ids': app_ids,
            'apify_token': apify_token,
            'start_date': start_date + 'T00:00:00Z'
        }

        streams_configuration = {
            'reviews': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class SurveyMonkey(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'SurveyMonkey', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int,
            access_token: str, client_id: Optional[str] = None, client_secret: Optional[str] = None,
            survey_ids: Optional[List[str]] = None, origin: Optional[str] = None,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'credentials': {
                'auth_method': 'oauth2.0',
                'access_token': access_token
            },
            'start_date': start_date
        }

        if client_id:
            source_configuration['credentials']['client_id'] = client_id
        if client_secret:
            source_configuration['credentials']['client_secret'] = client_secret
        if survey_ids:
            source_configuration['survey_ids'] = survey_ids
        if origin:
            source_configuration['origin'] = origin

        streams_configuration = {
            'surveys': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'survey_responses': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'survey_pages': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
            },
            'survey_questions': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
            },
            'survey_collectors': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
            },
            'collectors': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class SurveySparrow(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'SurveySparrow', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, access_token: str,
            survey_ids: Optional[List[str]] = None,
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        source_configuration = {
            'region': 'https://api.surveysparrow.com/v3',
            'access_token': access_token
        }
        if survey_ids is not None:
            source_configuration['survey_id'] = survey_ids
        streams_configuration = {
            'surveys': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class TrustpilotScraper(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Trustpilot Scraper', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, app_name: str,
            start_date: Optional[str] = None,
            timeout_milliseconds: Optional[int] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'app_name': app_name,
            'start_date': start_date
        }
        if timeout_milliseconds is not None:
            source_configuration['timeout_milliseconds'] = timeout_milliseconds

        streams_configuration = {
            'reviews': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class TwitterMentions(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Twitter Mentions', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, bearer_token: str, mentions: List[str],
            start_date: Optional[str] = None,
            timeout_milliseconds: Optional[int] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%d')

        source_configuration = {
            'bearer_token': bearer_token,
            'mentions': mentions,
            'start_date': start_date,
        }
        if timeout_milliseconds is not None:
            source_configuration['timeout_milliseconds'] = timeout_milliseconds

        streams_configuration = {
            'tweets': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class Typeform(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Typeform', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, access_token: str,
            start_date: Optional[str] = None,
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'
        source_configuration = {
            'start_date': start_date + 'T00:00:00Z',
            'credentials': {
                "auth_type": "access_token",
                "access_token": access_token
            }
        }
        streams_configuration = {
            'responses': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class ZendeskSupport(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Zendesk Support', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, subdomain: str, credentials: Mapping[str, Any],
            start_date: Optional[str] = None,
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'

        source_configuration = {
            'subdomain': subdomain,
            'start_date': start_date + 'T00:00:00Z',
            'credentials': credentials
        }

        streams_configuration = {
            'satisfaction_ratings': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append'
            },
            'ticket_audits': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'ticket_fields': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)
