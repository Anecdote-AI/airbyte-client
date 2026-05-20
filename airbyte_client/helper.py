import time
from datetime import datetime, timedelta
from typing import Mapping, Any, List, Optional, Tuple

import requests

from airbyte_client.client import Base, Client


class Helper(Base):

    def _parse_discover_schema_error(self, data: Mapping[str, Any]) -> Mapping[str, Any]:
        """Parse specific error patterns from discover schema response and return appropriate error messages."""
        
        # Check if there's job info with failure reason
        if 'jobInfo' in data and 'failureReason' in data['jobInfo']:
            failure_reason = data['jobInfo']['failureReason']
            internal_message = failure_reason.get('internalMessage', '')
            
            # Check for date format errors
            if 'time data' in internal_message and 'does not match format' in internal_message:
                # Extract the problematic date and expected format from the error
                if '%Y-%m-%dT%H:%M:%SZ' in internal_message:
                    return {
                        'error_code': 400,
                        'error_str': 'Invalid date format: start_date must be in ISO format (YYYY-MM-DDTHH:MM:SSZ), e.g., "2021-01-01T00:00:00Z"'
                    }
                else:
                    return {
                        'error_code': 400,
                        'error_str': f'Date format error: {internal_message}'
                    }
            
            # Check for authentication errors
            if 'auth' in internal_message.lower() or 'token' in internal_message.lower() or 'credential' in internal_message.lower():
                return {
                    'error_code': 401,
                    'error_str': f'Authentication error: {internal_message}'
                }
            
            # Check for configuration errors
            if 'config' in internal_message.lower():
                return {
                    'error_code': 400,
                    'error_str': f'Configuration error: {internal_message}'
                }
            
            # Check for connection errors
            if 'connection' in internal_message.lower() or 'network' in internal_message.lower() or 'timeout' in internal_message.lower():
                return {
                    'error_code': 503,
                    'error_str': f'Connection error: {internal_message}'
                }
            
            # Return the internal message if available but no specific pattern matched
            if internal_message:
                return {
                    'error_code': 500,
                    'error_str': f'Connector error: {internal_message}'
                }
        
        # Check for logs with error messages
        if 'logs' in data and 'events' in data['logs']:
            for event in data['logs']['events']:
                if event.get('level') == 'error':
                    error_message = event.get('message', '')
                    if 'time data' in error_message and 'does not match format' in error_message:
                        if '%Y-%m-%dT%H:%M:%SZ' in error_message:
                            return {
                                'error_code': 400,
                                'error_str': 'Invalid date format: start_date must be in ISO format (YYYY-MM-DDTHH:MM:SSZ), e.g., "2021-01-01T00:00:00Z"'
                            }
        
        # Default generic error if no specific pattern is found
        return {
            'error_code': 500,
            'error_str': 'Internal error: no streams in Airbyte discover schema response. Please, retry later'
        }

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
                # print(data)
                # Check for specific error patterns in the response
                err = self._parse_discover_schema_error(data)
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
            airbyte_client, 'Anecdote Surveys', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, project_id: int, admin_psk: str,
            base_url: str = 'https://api.anecdoteai.com', start_date: Optional[str] = None
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
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)

class ApifyFacebookPosts(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Apify Facebook Posts', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int,
            apify_token: str, start_urls: List[str],
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%d')

        source_configuration = {
            'apify_token': apify_token,
            'start_urls': start_urls,
            'start_date': start_date,
        }

        streams_configuration = {
            'posts': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)

class ApifyInstagramPosts(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Apify Instagram Posts', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int,
            apify_token: str, start_urls: List[str],
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%d')

        source_configuration = {
            'apify_token': apify_token,
            'start_urls': start_urls,
            'start_date': start_date,
        }

        streams_configuration = {
            'posts': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
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
            start_date = '2024-06-01T00:00:00Z'

        source_configuration = {
            'api_key': delighted_api_key,
            'since': start_date,
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
    

class IntercomConversations(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Intercom Conversations', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )
        # Create metadata connection handler with modified parameters
        metadata_bucket_name = "anecdote-dwh-metadata-bucket"
        # No change in path format and schedule
        metadata_path_format = s3_path_format
        metadata_schedule = schedule
        
        self.metadata_connection = IntercomConversationsMetadata(
            airbyte_client, source_definition_id, destination_definition_id,
            metadata_bucket_name, s3_bucket_region, s3_format,
            metadata_schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, metadata_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, access_token: str,
            start_date: Optional[str] = None, excluded_names: Optional[List[str]] = None, 
            excluded_emails: Optional[List[str]] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        metadata_start_date = '2000-01-01'

        # First create the metadata connection
        metadata_response, metadata_error = self.metadata_connection.enable(
            workspace_id, customer_name, ind, access_token,
            metadata_start_date, excluded_names, excluded_emails
        )
        
        if metadata_error is not None:
            return metadata_response, metadata_error

        # Then create the main conversations connection
        source_configuration = {
            'access_token': access_token,
            'start_date': start_date,
        }
        if excluded_names is not None:
            source_configuration['excluded_names'] = excluded_names
        if excluded_emails is not None:
            source_configuration['excluded_emails'] = excluded_emails

        streams_configuration = {
            'conversations': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        # First disable the metadata connection
        metadata_response, metadata_error = self.metadata_connection.disable(workspace_id, customer_name, ind)
        if metadata_error is not None:
            return metadata_response, metadata_error
            
        # Then disable the main connection
        return self.disconnect(workspace_id, ind)
    
class IntercomConversationsMetadata(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Intercom Conversations Metadata', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )
        self.schedule = schedule

    @staticmethod
    def transform_name(name: str) -> str:
        return name.lower().replace(' ', '-').replace('\t', '-') \
            .replace('\n', '-').replace('\r', '-').replace('_', '-')

    def connect(
            self, workspace_id: str, customer_name: str, ind: int,
            source_configuration: Mapping[str, Any],
            streams_configuration: Mapping[str, Any]
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        name = 'intercom-conversations'
        customer_name = self.transform_name(customer_name)

        self.destination_configuration['s3_bucket_path'] = \
            'source-name={}/customer-name={}/source-index={}'.format(
                name, customer_name, ind
            )
        
        # If schedule is not set, set it to a default value
        if self.schedule is None:
            self.schedule = {
                "schedule_type": "cron",
                "schedule_data": {
                    "cron": {
                        "cronTimeZone": "UTC",
                        "cronExpression": "0 0 * * * ?"
                    }
                }
            }

        connection_name = self.name + ' | ' + str(ind)
        response, error_map = self.connection_create_safe_full(
            workspace_id, connection_name,
            'destination', '${SOURCE_NAMESPACE}', '',
            self.source_definition_id, source_configuration,
            self.destination_definition_id, self.destination_configuration,
            streams_configuration,
            'active',
            schedule_type=self.schedule.get("schedule_type"),
            schedule_data=self.schedule.get("schedule_data")
        )
        return response, error_map

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, access_token: str,
            start_date: Optional[str] = None, excluded_names: Optional[List[str]] = None, 
            excluded_emails: Optional[List[str]] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2024-12-01'

        source_configuration = {
            'access_token': access_token,
            'start_date': start_date,
        }
        if excluded_names is not None:
            source_configuration['excluded_names'] = excluded_names
        if excluded_emails is not None:
            source_configuration['excluded_emails'] = excluded_emails

        streams_configuration = {
            'contacts': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'tags': {
                'syncMode': 'full_refresh',
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

class RedditApi(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Reddit Api', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, subreddits: List[str], client_id: str,
            client_secret: str, username: str, password: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2022-01-01'
        if 'T' not in start_date:
            start_date += 'T00:00:00Z'

        source_configuration = {
            'subreddits': subreddits,
            'client_id': client_id,
            'client_secret': client_secret,
            'username': username,
            'password': password,
            'start_date': start_date,
        }

        streams_configuration = {
            'comments': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'posts': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }
        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)


class Discourse(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Discourse', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, base_url: str,
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            # Ensure start_date is in the correct format
            if 'T' not in start_date:
                start_date = start_date + 'T00:00:00Z'
            elif not start_date.endswith('Z'):
                start_date = start_date + 'Z'

        source_configuration = {
            'base_url': base_url,
            'start_date': start_date,
        }

        streams_configuration = {
            'categories': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
            },
            'topics': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'posts': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'tags': {
                'syncMode': 'full_refresh',
                'destinationSyncMode': 'overwrite',
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

class Tiktok(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Tiktok', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int,
            apify_token: str, profiles: List[str],
            start_date: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%d')

        source_configuration = {
            'apify_token': apify_token,
            'profiles': profiles,
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
            self, workspace_id: str, customer_name: str, ind: int, bearer_token: str, search_query: str,
            start_date: Optional[str] = None,
            timeout_milliseconds: Optional[int] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%d')

        source_configuration = {
            'bearer_token': bearer_token,
            'search_query': search_query,
            'start_date': start_date,
        }
        if timeout_milliseconds is not None:
            source_configuration['timeout_milliseconds'] = timeout_milliseconds
        else:
            source_configuration['timeout_milliseconds'] = 3000

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



class TwitterTweets(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Twitter Tweets', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, apify_api_token: str, search_query: str,
            start_date: Optional[str] = None,
            timeout_milliseconds: Optional[int] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%d')

        source_configuration = {
            'apify_api_token': apify_api_token,
            'search_query': search_query,
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


class ZendeskConversations(AnecdoteConnection):
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None
    ):
        super().__init__(
            airbyte_client, 'Zendesk Conversations', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, subdomain: str, credentials: Mapping[str, Any],
            use_search_endpoint: Optional[bool] = None, query: Optional[str] = None,
            start_date: Optional[str] = None,
            update_database: Optional[bool] = None, source_id: Optional[int] = None,
            db_host: Optional[str] = None, db_port: Optional[str] = None,
            db_name: Optional[str] = None, db_user: Optional[str] = None,
            db_password: Optional[str] = None
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.today() - timedelta(days=6)).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            if 'T' not in start_date:
                start_date = start_date + 'T00:00:00Z'
            elif not start_date.endswith('Z'):
                start_date = start_date + 'Z'

        if use_search_endpoint is None:
            use_search_endpoint = False
        if (use_search_endpoint == True) and (query is None or query == ''):
            raise ValueError("query is required when use_search_endpoint is True")

        source_configuration = {
            'subdomain': subdomain,
            'credentials': credentials,
            'start_date': start_date,
            'use_search_endpoint': use_search_endpoint,
            'query': query,
        }

        if update_database:
            source_configuration['update_database'] = update_database
            source_configuration['source_id'] = source_id
            source_configuration['db_host'] = db_host
            source_configuration['db_port'] = db_port
            source_configuration['db_name'] = db_name
            source_configuration['db_user'] = db_user
            source_configuration['db_password'] = db_password

        streams_configuration = {
            'conversations': {
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
        
        # Create metadata connection handlers
        metadata_bucket_name = "anecdote-dwh-metadata-bucket"
        metadata_path_format = """${NAMESPACE}/year=${YEAR}/month=${MONTH}/day=${DAY}/${EPOCH}_"""
        # No change in schedule
        metadata_schedule = schedule

        metadata_s3_format = {
            'format_type': 'Parquet',
            'page_size_kb': 1024,
            'block_size_mb': 255,
            'compression_codec': 'GZIP',
            'dictionary_encoding': True,
            'max_padding_size_mb': 8,
            'dictionary_page_size_kb': 1024
        }
        
        # Initialize metadata handlers for different streams
        self.metadata_handlers = {
            'users': ZendeskSupportUsersMetadata(
                airbyte_client, source_definition_id, destination_definition_id,
                metadata_bucket_name, s3_bucket_region, metadata_s3_format,
                metadata_schedule, s3_access_key_id, s3_secret_access_key,
                s3_endpoint, metadata_path_format, s3_file_name_pattern
            ),
            'brands': ZendeskSupportBrandsMetadata(
                airbyte_client, source_definition_id, destination_definition_id,
                metadata_bucket_name, s3_bucket_region, metadata_s3_format,
                metadata_schedule, s3_access_key_id, s3_secret_access_key,
                s3_endpoint, metadata_path_format, s3_file_name_pattern
            ),
            'groups': ZendeskSupportGroupsMetadata(
                airbyte_client, source_definition_id, destination_definition_id,
                metadata_bucket_name, s3_bucket_region, metadata_s3_format,
                metadata_schedule, s3_access_key_id, s3_secret_access_key,
                s3_endpoint, metadata_path_format, s3_file_name_pattern
            ),
            'organization_memberships': ZendeskSupportOrgMembershipsMetadata(
                airbyte_client, source_definition_id, destination_definition_id,
                metadata_bucket_name, s3_bucket_region, metadata_s3_format,
                metadata_schedule, s3_access_key_id, s3_secret_access_key,
                s3_endpoint, metadata_path_format, s3_file_name_pattern
            ),
            'ticket_fields': ZendeskSupportTicketFieldsMetadata(
                airbyte_client, source_definition_id, destination_definition_id,
                metadata_bucket_name, s3_bucket_region, metadata_s3_format,
                metadata_schedule, s3_access_key_id, s3_secret_access_key,
                s3_endpoint, metadata_path_format, s3_file_name_pattern
            )
        }

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, subdomain: str, credentials: Mapping[str, Any],
            start_date: Optional[str] = None,
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        metadata_start_date = '2000-01-01'

        # First enable all metadata connections        
        for handler in self.metadata_handlers.values():
            metadata_response, metadata_error = handler.enable(
                workspace_id, customer_name, ind, subdomain, credentials,
                metadata_start_date
            )
            if metadata_error is not None:
                return metadata_response, metadata_error

        # Then enable the main connection
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
            'tickets': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'ticket_comments': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            },
            'ticket_metrics': {
                'syncMode': 'incremental',
                'destinationSyncMode': 'append',
            }
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        # First disable all metadata connections
        for handler in self.metadata_handlers.values():
            metadata_response, metadata_error = handler.disable(workspace_id, customer_name, ind)
            if metadata_error is not None:
                return metadata_response, metadata_error
                
        # Then disable the main connection
        return self.disconnect(workspace_id, ind)


class ZendeskSupportMetadataBase(AnecdoteConnection):
    """Base class for all Zendesk Support metadata connections"""
    
    def __init__(
            self, airbyte_client: Client, source_definition_id: str, destination_definition_id: str,
            s3_bucket_name: str, s3_bucket_region: str, s3_format: Mapping[str, Any],
            schedule: Optional[Mapping[str, Any]] = None,
            s3_access_key_id: Optional[str] = None, s3_secret_access_key: Optional[str] = None,
            s3_endpoint: Optional[str] = None, s3_path_format: Optional[str] = None,
            s3_file_name_pattern: Optional[str] = None,
            stream_name: str = None
    ):
        super().__init__(
            airbyte_client, 'Zendesk Support Metadata', source_definition_id, destination_definition_id,
            s3_bucket_name, s3_bucket_region, s3_format,
            schedule,
            s3_access_key_id, s3_secret_access_key,
            s3_endpoint, s3_path_format,
            s3_file_name_pattern
        )
        self.stream_name = stream_name
        self.schedule = schedule

    def get_stream_config(self) -> Mapping[str, Any]:
        """Template method to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement get_stream_config")

    def get_connection_name_suffix(self) -> str:
        """Template method to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement get_connection_name_suffix")

    @staticmethod
    def transform_name(name: str) -> str:
        return name.lower().replace(' ', '-').replace('\t', '-') \
            .replace('\n', '-').replace('\r', '-').replace('_', '-')

    def connect(
            self, workspace_id: str, customer_name: str, ind: int,
            source_configuration: Mapping[str, Any],
            streams_configuration: Mapping[str, Any]
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        name = 'zendesk-support'
        customer_name = self.transform_name(customer_name)

        self.destination_configuration['s3_bucket_path'] = \
            '{}/source-name={}/customer-name={}/source-index={}'.format(
                self.stream_name, name, customer_name, ind
            )
        
        # If schedule is not set, set it to a default value
        if self.schedule is None:
            self.schedule = {
                "schedule_type": "cron",
                "schedule_data": {
                    "cron": {
                        "cronTimeZone": "UTC",
                        "cronExpression": "0 0 * * * ?"
                    }
                }
            }

        connection_name = self.name + ' ' + self.get_connection_name_suffix() + ' | ' + str(ind)
        response, error_map = self.connection_create_safe_full(
            workspace_id, connection_name,
            'destination', '${SOURCE_NAMESPACE}', '',
            self.source_definition_id, source_configuration,
            self.destination_definition_id, self.destination_configuration,
            streams_configuration,
            'active',
            schedule_type=self.schedule.get("schedule_type"),
            schedule_data=self.schedule.get("schedule_data")
        )
        return response, error_map

    def enable(
            self, workspace_id: str, customer_name: str, ind: int, subdomain: str, credentials: Mapping[str, Any],
            start_date: Optional[str] = None,
    ) -> Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        if start_date is None:
            start_date = '2000-01-01'

        source_configuration = {
            'subdomain': subdomain,
            'start_date': start_date + 'T00:00:00Z',
            'credentials': credentials
        }

        streams_configuration = {
            self.stream_name: self.get_stream_config()
        }

        return self.connect(workspace_id, customer_name, ind, source_configuration, streams_configuration)

    def disable(self, workspace_id: str, customer_name: str, ind: int) -> \
            Tuple[Optional[requests.Response], Optional[Mapping[str, Any]]]:
        return self.disconnect(workspace_id, ind)
        

class ZendeskSupportUsersMetadata(ZendeskSupportMetadataBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, stream_name='users', **kwargs)

    def get_stream_config(self) -> Mapping[str, Any]:
        return {
            'syncMode': 'incremental',
            'destinationSyncMode': 'append'
        }

    def get_connection_name_suffix(self) -> str:
        return 'Users'

class ZendeskSupportBrandsMetadata(ZendeskSupportMetadataBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, stream_name='brands', **kwargs)

    def get_stream_config(self) -> Mapping[str, Any]:
        return {
            'syncMode': 'full_refresh',
            'destinationSyncMode': 'append'
        }

    def get_connection_name_suffix(self) -> str:
        return 'Brands'

class ZendeskSupportGroupsMetadata(ZendeskSupportMetadataBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, stream_name='groups', **kwargs)

    def get_stream_config(self) -> Mapping[str, Any]:
        return {
            'syncMode': 'incremental',
            'destinationSyncMode': 'append'
        }

    def get_connection_name_suffix(self) -> str:
        return 'Groups'

class ZendeskSupportOrgMembershipsMetadata(ZendeskSupportMetadataBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, stream_name='organization_memberships', **kwargs)

    def get_stream_config(self) -> Mapping[str, Any]:
        return {
            'syncMode': 'incremental',
            'destinationSyncMode': 'append'
        }

    def get_connection_name_suffix(self) -> str:
        return 'Organization Memberships'

class ZendeskSupportTicketFieldsMetadata(ZendeskSupportMetadataBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, stream_name='ticket_fields', **kwargs)

    def get_stream_config(self) -> Mapping[str, Any]:
        return {
            'syncMode': 'incremental',
            'destinationSyncMode': 'append'
        }

    def get_connection_name_suffix(self) -> str:
        return 'Ticket Fields'




