import os

from charmhelpers.core import hookenv
from charms.reactive import set_flag, clear_flag, endpoint_from_flag, when, when_not
from charms import layer


@when('charm.kubeflow-seldon-api-frontend.started')
def charm_ready():
    layer.status.active('')


@when('layer.docker-resource.oci-image.changed', 'config.changed')
def update_image():
    clear_flag('charm.kubeflow-seldon-api-frontend.started')


@when_not('endpoint.redis.available')
def blocked():
    goal_state = hookenv.goal_state()
    if 'redis' in goal_state['relations']:
        layer.status.waiting('waiting for redis')
    else:
        layer.status.blocked('missing relation to redis')
    clear_flag('charm.kubeflow-seldon-api-frontend.started')


@when('layer.docker-resource.oci-image.available')
@when('endpoint.redis.available')
@when_not('charm.kubeflow-seldon-api-frontend.started')
def start_charm(redis):
    layer.status.maintenance('configuring container')

    image_info = layer.docker_resource.get_info('oci-image')

    rest_port = hookenv.config('rest-port')
    grpc_port = hookenv.config('grpc-port')

    layer.caas_base.pod_spec_set(
        {
            'containers': [
                {
                    'name': 'seldon-apiserver',
                    'imageDetails': {
                        'imagePath': image_info.registry_path,
                        'username': image_info.username,
                        'password': image_info.password,
                    },
                    'ports': [
                        {'name': 'rest', 'containerPort': rest_port},
                        {'name': 'grpc', 'containerPort': grpc_port},
                    ],
                    'config': {
                        'SELDON_CLUSTER_MANAGER_REDIS_HOST': redis.all_joined_units[
                            0
                        ].application_name,
                        'SELDON_CLUSTER_MANAGER_POD_NAMESPACE': os.environ['JUJU_MODEL_NAME'],
                        'SELDON_ENGINE_KAFKA_SERVER': 'kafka:9092',
                        'SELDON_SINGLE_NAMESPACE': True,
                    },
                }
            ]
        }
    )

    layer.status.maintenance('creating container')
    set_flag('charm.kubeflow-seldon-api-frontend.started')
