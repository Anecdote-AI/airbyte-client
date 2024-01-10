from typing import Union, List, Mapping, Any, Optional

import requests


class Workspaces:
    pass


class SourceDefinitions:
    pass


class SourceDefinitionSpecifications:
    pass


class Sources:
    pass


class DestinationDefinitions:
    pass


class DestinationDefinitionSpecifications:
    pass


class Destinations:
    pass


class Connections:
    pass


# TODO
class DestinationOAuths:
    pass


# TODO
class SourceOAuths:
    pass


# TODO
class DBMigrations:
    pass


class Health:
    pass


# TODO
class Attempt:
    pass


# TODO
class State:
    pass


# TODO
class Notifications:
    pass


# TODO
class Internal:
    pass


# TODO
class Operations:
    pass


# TODO
class Scheduler:
    pass


# TODO
class Jobs:
    pass


# TODO
class Logs:
    pass


class Client:
    __POST = 'POST'
    __GET = 'GET'

    def __init__(self, https: bool, host: str, port: int, token: str, prefix: str = 'api/v1/',
                 timeout_ms: int = 100000):
        self.https = https
        self.host = host
        self.port = port
        self.token = token
        self.prefix = prefix
        self.timeout_ms = timeout_ms

        self.base_url = '{}://{}:{}/{}'.format(
            'https' if https else 'http', host, port, prefix
        )
        self.headers = {
            'Authorization': 'Bearer {}'.format(token)
        }

    def base_request(self, path: str, json: Optional[Union[dict, str, list]] = None,
                     method: str = 'POST') -> requests.Response:
        try:
            response = requests.request(method, self.base_url + path, headers=self.headers, json=json,
                                        timeout=self.timeout_ms / 1000.0)
        except Exception as e:
            response = requests.Response()
            response.status_code = 524
        return response

    def workspaces(self) -> Workspaces:
        return Workspaces(
            Client(self.https, self.host, self.port, self.token, self.prefix + 'workspaces/'))

    def source_definitions(self) -> SourceDefinitions:
        return SourceDefinitions(
            Client(self.https, self.host, self.port, self.token, self.prefix + 'source_definitions/'))

    def source_definition_specifications(self) -> SourceDefinitionSpecifications:
        return SourceDefinitionSpecifications(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'source_definition_specifications/'))

    def sources(self) -> Sources:
        return Sources(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'sources/'))

    def destination_definitions(self) -> DestinationDefinitions:
        return DestinationDefinitions(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'destination_definitions/'))

    def destination_definition_specifications(self) -> DestinationDefinitionSpecifications:
        return DestinationDefinitionSpecifications(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'destination_definition_specifications/'))

    def destinations(self) -> Destinations:
        return Destinations(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'destinations/'))

    def connections(self) -> Connections:
        return Connections(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'connections/'))

    def destination_oauths(self) -> DestinationOAuths:
        return DestinationOAuths(Client(self.https, self.host, self.port, self.token,
                                        self.prefix + 'destination_oauths/'))

    def source_oauths(self) -> SourceOAuths:
        return SourceOAuths(Client(self.https, self.host, self.port, self.token,
                                   self.prefix + 'source_oauths/'))

    def health(self) -> Health:
        return Health(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'health/'))

    def attempt(self) -> Attempt:
        return Attempt(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'attempt/'))

    def state(self) -> State:
        return State(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'state/'))

    def notifications(self) -> Notifications:
        return Notifications(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'notifications/'))

    def internal(self) -> Internal:
        return Internal(Client(self.https, self.host, self.port, self.token, self.prefix))

    def operations(self) -> Operations:
        return Operations(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'operations/'))

    def scheduler(self) -> Scheduler:
        return Scheduler(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'scheduler/'))

    def jobs(self) -> Jobs:
        return Jobs(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'jobs/'))

    def logs(self) -> Logs:
        return Logs(
            Client(self.https, self.host, self.port, self.token,
                   self.prefix + 'logs/'))


class Base:
    def __init__(self, cli: Client,
                 timeout_between_requests_ms: int = 0,
                 timeout_before_schema_discovery_ms: int = 0,
                 max_check_retries: int = 10):
        self.airbyte_client = cli
        self.timeout_between_requests_ms = timeout_between_requests_ms
        self.timeout_before_schema_discovery_ms = timeout_before_schema_discovery_ms
        self.max_retries = max_check_retries


class Workspaces(Base):
    def create(self, name: str,
               email: Union[str, None] = None,
               webhook_url: Union[str, None] = None
               ) -> requests.Response:
        return self.airbyte_client.base_request('create', {
            'email': email,
            'anonymousDataCollection': True,
            'name': name,
            'news': True,
            'securityUpdates': True,
            'notifications': [],
            'notificationSettings': {
                'sendOnSuccess': {
                    'notificationType': [
                        'slack'
                    ],
                    'slackConfiguration': {
                        'webhook': webhook_url
                    }
                },
                'sendOnFailure': {
                    'notificationType': [
                        'slack'
                    ],
                    'slackConfiguration': {
                        'webhook': webhook_url
                    }
                },
                'sendOnSyncDisabled': {
                    'notificationType': [
                        'customerio'
                    ]
                },
                'sendOnSyncDisabledWarning': {
                    'notificationType': [
                        'customerio'
                    ]
                },
                'sendOnConnectionUpdate': {
                    'notificationType': [
                        'customerio'
                    ]
                },
                'sendOnConnectionUpdateActionRequired': {
                    'notificationType': [
                        'customerio'
                    ]
                }
            },
            'displaySetupWizard': True,
            'defaultGeography': 'auto',
        })

    def delete(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('delete', {
            'workspaceId': workspace_id
        })

    def list(self) -> requests.Response:
        return self.airbyte_client.base_request('list')

    def get(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'workspaceId': workspace_id
        })

    def get_by_slug(self, slug: str) -> requests.Response:
        return self.airbyte_client.base_request('get_by_slug', {
            'slug': slug
        })

    def get_by_connection_id(self, connection_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get_connection_id', {
            'connectionId': connection_id
        })

    def update(self, workspace_id: str,
               email: Union[str, None] = None,
               webhook_url: Union[str, None] = None
               ) -> requests.Response:
        return self.airbyte_client.base_request('update', {
            'workspaceId': workspace_id,
            'email': email,
            'anonymousDataCollection': True,
            'news': True,
            'securityUpdates': True,
            'notifications': [],
            'notificationSettings': {
                'sendOnSuccess': {
                    'notificationType': [
                        'slack'
                    ],
                    'slackConfiguration': {
                        'webhook': webhook_url
                    }
                },
                'sendOnFailure': {
                    'notificationType': [
                        'slack'
                    ],
                    'slackConfiguration': {
                        'webhook': webhook_url
                    }
                },
                'sendOnSyncDisabled': {
                    'notificationType': [
                        'customerio'
                    ]
                },
                'sendOnSyncDisabledWarning': {
                    'notificationType': [
                        'customerio'
                    ]
                },
                'sendOnConnectionUpdate': {
                    'notificationType': [
                        'customerio'
                    ]
                },
                'sendOnConnectionUpdateActionRequired': {
                    'notificationType': [
                        'customerio'
                    ]
                }
            },
            'displaySetupWizard': True,
            'defaultGeography': 'auto',
        })

    def update_name(self, workspace_id: str, name: str) -> requests.Response:
        return self.airbyte_client.base_request('update_name', {
            'workspaceId': workspace_id,
            'name': name
        })

    def tag_feedback_status_as_done(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('tag_feedback_status_as_done', {
            'workspaceId': workspace_id
        })


class SourceDefinitions(Base):
    def create(self, name: str, docker_repository: str, docker_image_tag: str, documentation_url: str,
               icon: Union[str, None] = None,
               resource_requirements: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {
            'name': name,
            'dockerRepository': docker_repository,
            'dockerImageTag': docker_image_tag,
            'documentationUrl': documentation_url
        }
        if icon is not None:
            data['icon'] = icon
        if resource_requirements is not None:
            data['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('create', data)

    def update(self, source_definition_id: str, docker_image_tag: str,
               resource_requirements: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {
            'sourceDefinitionId': source_definition_id,
            'dockerImageTag': docker_image_tag
        }
        if resource_requirements is not None:
            data['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('update', data)

    def list(self) -> requests.Response:
        return self.airbyte_client.base_request('list')

    def list_latest(self) -> requests.Response:
        return self.airbyte_client.base_request('list_latest')

    def get(self, source_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'sourceDefinitionId': source_definition_id
        })

    def delete(self, source_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('delete', {
            'sourceDefinitionId': source_definition_id
        })

    def list_private(self) -> requests.Response:
        return self.airbyte_client.base_request('list_private')

    def list_for_workspace(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('list_for_workspace', {
            'workspaceId': workspace_id
        })

    def create_custom(self, workspace_id: str,
                      name: str, docker_repository: str, docker_image_tag: str, documentation_url: str,
                      icon: Union[str, None] = None,
                      resource_requirements: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {
            'workspaceId': workspace_id,
            'sourceDefinition': {
                'name': name,
                'dockerRepository': docker_repository,
                'dockerImageTag': docker_image_tag,
                'documentationUrl': documentation_url,
            }
        }
        if icon is not None:
            data['sourceDefinition']['icon'] = icon
        if resource_requirements is not None:
            data['sourceDefinition']['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('create_custom', data)

    def get_for_workspace(self, workspace_id: str, source_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get_for_workspace', {
            'workspaceId': workspace_id,
            'sourceDefinitionId': source_definition_id
        })

    def update_custom(self, workspace_id: str, source_definition_id: str, docker_image_tag: str,
                      resource_requirements: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {
            'workspaceId': workspace_id,
            'sourceDefinition': {
                'sourceDefinitionId': source_definition_id,
                'dockerImageTag': docker_image_tag
            }
        }
        if resource_requirements is not None:
            data['sourceDefinition']['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('update', data)

    def delete_custom(self, workspace_id: str, source_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('delete_custom', {
            'workspaceId': workspace_id,
            'sourceDefinitionId': source_definition_id
        })

    def grant_definition(self, workspace_id: str, source_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('grant_definition', {
            'workspaceId': workspace_id,
            'sourceDefinitionId': source_definition_id
        })

    def revoke_definition(self, workspace_id: str, source_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('revoke_definition', {
            'workspaceId': workspace_id,
            'sourceDefinitionId': source_definition_id
        })


class SourceDefinitionSpecifications(Base):
    def get(self, workspace_id: str, source_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'workspaceId': workspace_id,
            'sourceDefinitionId': source_definition_id
        })


class Sources(Base):
    def create(self, workspace_id: str, source_definition_id: str, name: str,
               connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('create', {
            'workspaceId': workspace_id,
            'sourceDefinitionId': source_definition_id,
            'name': name,
            'connectionConfiguration': connection_configuration
        })

    def update(self, source_id: str, name: str,
               connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('update', {
            'sourceId': source_id,
            'name': name,
            'connectionConfiguration': connection_configuration
        })

    def list(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('list', {
            'workspaceId': workspace_id
        })

    def get(self, source_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'sourceId': source_id
        })

    def search(self, workspace_id: Union[str, None] = None, source_definition_id: Union[str, None] = None,
               name: Union[str, None] = None,
               source_id: Union[str, None] = None, source_name: Union[str, None] = None,
               connection_configuration: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {}
        if workspace_id is not None:
            data['workspaceId'] = workspace_id
        if source_definition_id is not None:
            data['sourceDefinitionId'] = source_definition_id
        if name is not None:
            data['name'] = name
        if source_id is not None:
            data['sourceId'] = source_id
        if source_name is not None:
            data['sourceName'] = source_name
        if connection_configuration is not None:
            data['connectionConfiguration'] = connection_configuration
        return self.airbyte_client.base_request('search', data)

    def clone(self, source_clone_id: str, name: str, connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('clone', {
            'sourceCloneId': source_clone_id,
            'sourceConfiguration': {
                'name': name,
                'connectionConfiguration': connection_configuration
            }
        })

    def delete(self, source_id: str) -> requests.Response:
        return self.airbyte_client.base_request('delete', {
            'sourceId': source_id
        })

    def check_connection(self, source_id: str) -> requests.Response:
        return self.airbyte_client.base_request('check_connection', {
            'sourceId': source_id
        })

    def check_connection_for_update(self, source_id: str, name: str,
                                    connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('check_connection_for_update', {
            'sourceId': source_id,
            'name': name,
            'connectionConfiguration': connection_configuration
        })

    def discover_schema(self, source_id: str, connection_id: Union[str, None] = None,
                        disable_cache: Union[bool, None] = None) -> requests.Response:
        data = {
            'sourceId': source_id,
        }
        if connection_id is not None:
            data['connectionId'] = connection_id
        if disable_cache is not None:
            data['disable_cache'] = disable_cache
        return self.airbyte_client.base_request('discover_schema', data)


class DestinationDefinitions(Base):
    def create(self, name: str, docker_repository: str, docker_image_tag: str, documentation_url: str,
               icon: Union[str, None] = None,
               resource_requirements: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {
            'name': name,
            'dockerRepository': docker_repository,
            'dockerImageTag': docker_image_tag,
            'documentationUrl': documentation_url
        }
        if icon is not None:
            data['icon'] = icon
        if resource_requirements is not None:
            data['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('create', data)

    def update(self, destination_definition_id: str, docker_image_tag: str,
               resource_requirements: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {
            'destinationDefinitionId': destination_definition_id,
            'dockerImageTag': docker_image_tag
        }
        if resource_requirements is not None:
            data['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('update', data)

    def list(self) -> requests.Response:
        return self.airbyte_client.base_request('list')

    def list_latest(self) -> requests.Response:
        return self.airbyte_client.base_request('list_latest')

    def get(self, destination_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'destinationDefinitionId': destination_definition_id
        })

    def delete(self, destination_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('delete', {
            'destinationDefinitionId': destination_definition_id
        })

    def list_private(self) -> requests.Response:
        return self.airbyte_client.base_request('list_private')

    def list_for_workspace(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('list_for_workspace', {
            'workspaceId': workspace_id
        })

    def create_custom(self, workspace_id: str,
                      name: str, docker_repository: str, docker_image_tag: str, documentation_url: str,
                      icon: Union[str, None] = None,
                      resource_requirements: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {
            'workspaceId': workspace_id,
            'destinationDefinition': {
                'name': name,
                'dockerRepository': docker_repository,
                'dockerImageTag': docker_image_tag,
                'documentationUrl': documentation_url,
            }
        }
        if icon is not None:
            data['destinationDefinition']['icon'] = icon
        if resource_requirements is not None:
            data['destinationDefinition']['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('create_custom', data)

    def get_for_workspace(self, workspace_id: str, destination_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get_for_workspace', {
            'workspaceId': workspace_id,
            'destinationDefinitionId': destination_definition_id
        })

    def update_custom(self, workspace_id: str, destination_definition_id: str, docker_image_tag: str,
                      resource_requirements: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {
            'workspaceId': workspace_id,
            'destinationDefinition': {
                'destinationDefinitionId': destination_definition_id,
                'dockerImageTag': docker_image_tag
            }
        }
        if resource_requirements is not None:
            data['destinationDefinition']['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('update', data)

    def delete_custom(self, workspace_id: str, destination_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('delete_custom', {
            'workspaceId': workspace_id,
            'destinationDefinitionId': destination_definition_id
        })

    def grant_definition(self, workspace_id: str, destination_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('grant_definition', {
            'workspaceId': workspace_id,
            'destinationDefinitionId': destination_definition_id
        })

    def revoke_definition(self, workspace_id: str, destination_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('revoke_definition', {
            'workspaceId': workspace_id,
            'destinationDefinitionId': destination_definition_id
        })


class DestinationDefinitionSpecifications(Base):
    def get(self, workspace_id: str, destination_definition_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'workspaceId': workspace_id,
            'destinationDefinitionId': destination_definition_id
        })


class Destinations(Base):
    def create(self, workspace_id: str, destination_definition_id: str, name: str,
               connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('create', {
            'workspaceId': workspace_id,
            'destinationDefinitionId': destination_definition_id,
            'name': name,
            'connectionConfiguration': connection_configuration
        })

    def update(self, destination_id: str, name: str,
               connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('update', {
            'destinationId': destination_id,
            'name': name,
            'connectionConfiguration': connection_configuration
        })

    def list(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('list', {
            'workspaceId': workspace_id
        })

    def get(self, destination_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'destinationId': destination_id
        })

    def search(self, workspace_id: Union[str, None] = None, destination_definition_id: Union[str, None] = None,
               name: Union[str, None] = None,
               destination_id: Union[str, None] = None, destination_name: Union[str, None] = None,
               connection_configuration: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {}
        if workspace_id is not None:
            data['workspaceId'] = workspace_id
        if destination_definition_id is not None:
            data['destinationDefinitionId'] = destination_definition_id
        if name is not None:
            data['name'] = name
        if destination_id is not None:
            data['destinationId'] = destination_id
        if destination_name is not None:
            data['destinationName'] = destination_name
        if connection_configuration is not None:
            data['connectionConfiguration'] = connection_configuration
        return self.airbyte_client.base_request('search', data)

    def check_connection(self, destination_id: str) -> requests.Response:
        return self.airbyte_client.base_request('check_connection', {
            'destinationId': destination_id
        })

    def check_connection_for_update(self, destination_id: str, name: str,
                                    connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('check_connection_for_update', {
            'destinationId': destination_id,
            'name': name,
            'connectionConfiguration': connection_configuration
        })

    def delete(self, destination_id: str) -> requests.Response:
        return self.airbyte_client.base_request('delete', {
            'destinationId': destination_id
        })

    def clone(self, destination_clone_id: str, name: str,
              connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('clone', {
            'destinationCloneId': destination_clone_id,
            'destinationConfiguration': {
                'name': name,
                'connectionConfiguration': connection_configuration
            }
        })


class Connections(Base):
    def create(self, name: str, namespace_definition: str, namespace_format: str, prefix: str,
               source_id: str, destination_id: str, streams: List[Mapping[str, Any]], status: str,
               operation_ids: Union[List[str], None] = None, schedule: Union[Mapping[str, Any], None] = None,
               schedule_type: Union[str, None] = None, schedule_data: Union[Mapping[str, Any], None] = None,
               resource_requirements: Union[Mapping[str, Any], None] = None,
               source_catalog_id: Union[str, None] = None) -> requests.Response:
        data = {
            'name': name,
            'namespaceDefinition': namespace_definition,
            'namespaceFormat': namespace_format,
            'prefix': prefix,
            'sourceId': source_id,
            'destinationId': destination_id,
            'syncCatalog': {
                'streams': streams
            },
            'status': status,
            'geography': 'auto'
        }

        if operation_ids is not None:
            data['operationIds'] = operation_ids
        if schedule is not None:
            data['schedule'] = schedule
        if schedule_type is not None:
            data['scheduleType'] = schedule_type
        if schedule_data is not None:
            data['scheduleData'] = schedule_data
        if resource_requirements is not None:
            data['resourceRequirements'] = resource_requirements
        if source_catalog_id is not None:
            data['sourceCatalogId'] = source_catalog_id

        return self.airbyte_client.base_request('create', data)

    def update(self, connection_id: str,
               namespace_definition: Optional[str] = None, namespace_format: Optional[str] = None,
               prefix: Optional[str] = None,
               source_id: Optional[str] = None, destination_id: Optional[str] = None,
               streams: Optional[List[Mapping[str, Any]]] = None, status: Optional[str] = None,
               operation_ids: Optional[List[str]] = None, schedule: Optional[Mapping[str, Any]] = None,
               schedule_type: Optional[str] = None, schedule_data: Optional[Mapping[str, Any]] = None,
               resource_requirements: Optional[Mapping[str, Any]] = None) -> requests.Response:
        data = {
            'connectionId': connection_id,
            'geography': 'auto'
        }

        if namespace_definition is not None:
            data['namespaceDefinition'] = namespace_definition
        if namespace_format is not None:
            data['namespaceFormat'] = namespace_format
        if prefix is not None:
            data['prefix'] = prefix
        if source_id is not None:
            data['sourceId'] = source_id
        if destination_id is not None:
            data['destinationId'] = destination_id
        if streams is not None:
            data['syncCatalog'] = {
                'streams': streams
            }
        if status is not None:
            data['status'] = status
        if operation_ids is not None:
            data['operationIds'] = operation_ids
        if schedule is not None:
            data['schedule'] = schedule
        if schedule_type is not None:
            data['scheduleType'] = schedule_type
        if schedule_data is not None:
            data['scheduleData'] = schedule_data
        if resource_requirements is not None:
            data['resourceRequirements'] = resource_requirements
        return self.airbyte_client.base_request('update', data)

    def list(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('list', {
            'workspaceId': workspace_id
        })

    def list_all(self, workspace_id: str) -> requests.Response:
        return self.airbyte_client.base_request('list_all', {
            'workspaceId': workspace_id
        })

    def get(self, connection_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'connectionId': connection_id
        })

    def search(self, connection_id: Union[str, None] = None, name: Union[str, None] = None,
               namespace_definition: Union[str, None] = None, namespace_format: Union[str, None] = None,
               prefix: Union[str, None] = None,
               source_id: Union[str, None] = None, destination_id: Union[str, None] = None,
               schedule: Union[Mapping[str, Any], None] = None,
               schedule_type: Union[str, None] = None, schedule_data: Union[Mapping[str, Any], None] = None,
               status: Union[str, None] = None,
               source: Union[Mapping[str, Any], None] = None,
               destination: Union[Mapping[str, Any], None] = None) -> requests.Response:
        data = {}
        if connection_id is not None:
            data['connectionId'] = connection_id
        if name is not None:
            data['name'] = name
        if namespace_definition is not None:
            data['namespaceDefinition'] = namespace_definition
        if namespace_format is not None:
            data['namespaceFormat'] = namespace_format
        if prefix is not None:
            data['prefix'] = prefix
        if source_id is not None:
            data['sourceId'] = source_id
        if destination_id is not None:
            data['destinationId'] = destination_id
        if schedule is not None:
            data['schedule'] = schedule
        if schedule_type is not None:
            data['scheduleType'] = schedule_type
        if schedule_data is not None:
            data['scheduleData'] = schedule_data
        if status is not None:
            data['status'] = status
        if source is not None:
            data['source'] = source
        if destination is not None:
            data['destination'] = destination
        return self.airbyte_client.base_request('search', data)

    def delete(self, connection_id: str) -> requests.Response:
        return self.airbyte_client.base_request('delete', {
            'connectionId': connection_id
        })

    def sync(self, connection_id: str) -> requests.Response:
        return self.airbyte_client.base_request('sync', {
            'connectionId': connection_id
        })

    def reset(self, connection_id: str) -> requests.Response:
        return self.airbyte_client.base_request('reset', {
            'connectionId': connection_id
        })


# TODO
class DestinationOAuths(Base):
    pass


# TODO
class SourceOAuths(Base):
    pass


# TODO
class DBMigrations(Base):
    pass


class Health(Base):
    def health(self) -> requests.Response:
        return self.airbyte_client.base_request('', method='GET')


# TODO
class Attempt(Base):
    pass


# TODO
class State(Base):
    pass


# TODO
class Notifications(Base):
    pass


# TODO
class Internal(Base):
    pass


# TODO
class Operations(Base):
    pass


# TODO
class Scheduler(Base):
    def sources_check_connection(self, workspace_id: str, source_definition_id: str,
                                 connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('sources/check_connection', {
            'workspaceId': workspace_id,
            'sourceDefinitionId': source_definition_id,
            'connectionConfiguration': connection_configuration
        })

    def sources_discover_schema(self, workspace_id: str, source_definition_id: str,
                                connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('sources/discover_schema', {
            'workspaceId': workspace_id,
            'sourceDefinitionId': source_definition_id,
            'connectionConfiguration': connection_configuration
        })

    def destinations_check_connection(self, workspace_id: str, destination_definition_id: str,
                                      connection_configuration: Mapping[str, Any]) -> requests.Response:
        return self.airbyte_client.base_request('destinations/check_connection', {
            'workspaceId': workspace_id,
            'destinationDefinitionId': destination_definition_id,
            'connectionConfiguration': connection_configuration
        })


# TODO
class Jobs(Base):
    def list(self, config_types: str, config_id: str,
             including_job_id: Optional[int] = None,
             pagination: Optional[Mapping[str, Any]] = None) -> requests.Response:
        data = {
            'configTypes': config_types,
            'configId': config_id
        }
        if including_job_id is not None:
            data['includingJobId'] = including_job_id
        if pagination is not None:
            data[' pagination'] = pagination
        return self.airbyte_client.base_request('list', data)

    def get(self, job_id: int) -> requests.Response:
        return self.airbyte_client.base_request('get', {
            'id': job_id
        })

    def get_last_replication_job(self, connection_id: str) -> requests.Response:
        return self.airbyte_client.base_request('get_last_replication_job', {
            'connectionId': connection_id
        })

    def get_light(self, job_id: int) -> requests.Response:
        return self.airbyte_client.base_request('get_light', {
            'id': job_id
        })

    def cancel(self, job_id: int) -> requests.Response:
        return self.airbyte_client.base_request('cancel', {
            'id': job_id
        })

    def get_debug_info(self, job_id: int) -> requests.Response:
        return self.airbyte_client.base_request('get_debug_info', {
            'id': job_id
        })

    def get_normalization_status(self, job_id: int) -> requests.Response:
        return self.airbyte_client.base_request('get_normalization_status', {
            'id': job_id
        })


# TODO
class Logs(Base):
    pass
