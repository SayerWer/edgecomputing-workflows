import requests
import time
import random

import docker
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

COMPONENT_CONFIG_MAP = {
    'compression': {
        'image': 'mayukuse2424/edgecomputing-compression',
        'internal_port': 5001,
        'target_port': 6000
    },
    'text_classification': {
        'image': 'quay.io/codait/max-toxic-comment-classifier',
        'internal_port': 5000,
        'target_port': 6001
    }
}

# TODO: switch to base class and inherit for each workflow
class WorkflowHandler():
    def __init__(self):
        self.swarm_client = docker.from_env()
        self.http_session = self._create_http_session()
        self.persist_service_spec_map = {}

    def _create_http_session(self):
        '''
        Using new session for every instance of workflow. This helps to reduce
        no. of tcp connections. It also provides a retry mechanism allowing
        newly created services/containers to start 
        '''
        retry_strategy = Retry(
            total=10,
            backoff_factor=1
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)

        http = requests.Session()
        http.mount("http://", adapter)

        return http

    def _send_request(self, app_port, path, payload):
        # TODO: use domain name instead of ips
        return self.http_session.post(
            'http://10.176.67.87:{port}{path}'.format(port=app_port, path=path),
            json=payload
        ).json()

    def create_service_temp(self, name, image, internal_port):
        random_port = random.randint(10000, 65500)

        endpoint_spec = docker.types.EndpointSpec(ports={random_port:internal_port})
        
        service = self.swarm_client.services.create(
            image=image,
            name='{name}-temp-{port}'.format(name=name, port=random_port),
            endpoint_spec=endpoint_spec
        )

        # TODO: Add service spec to map if persist=True
        service_spec = {
            'name': name,
            'port': random_port,
            'service_obj': service
        }

        return service_spec

    def create_service_persist(self, name):
        # Get service if already running
        service_spec = self.persist_service_spec_map.get(name, None)

        if service_spec is not None:
            # TODO: add check to see if service close to termination
            
            service_spec['last_updated'] = int(time.time() * 1000)

            return service_spec

        service_config = COMPONENT_CONFIG_MAP[name]

        target_port = service_config['target_port']

        endpoint_spec = docker.types.EndpointSpec(
            ports={ target_port:service_config['internal_port'] }
        )

        service = self.swarm_client.services.create(
            image=service_config['image'],
            name='{name}-persist-{port}'.format(name=name, port=target_port),
            endpoint_spec=endpoint_spec
        )

        service_spec = {
            'name': name,
            'port': target_port,
            'service_obj': service,
            'last_updated': int(time.time() * 1000)
        }

        self.persist_service_spec_map[name] = service_spec

        return service_spec

    def run_workflow_a_temp(self, input_data):
        print("Starting temporary workflow for audio surveillance")

        # TODO: create required docker containers
        print("Starting compression service")
        compress_spec = self.create_service_temp('compression', 'mayukuse2424/edgecomputing-compression', 5001)

        print("Starting text classification service")
        classifier_spec = self.create_service_temp('text_classification', 'quay.io/codait/max-toxic-comment-classifier', 5000)

        # TODO: Send request to component in order one-by-one and transform result
        # as required for next component
        print("Sending payload to compress")

        payload = {"type": "gzip","data": input_data}

        resp = self._send_request(compress_spec['port'], '/compress', payload)

        print("Compression response", resp)

        print("Sending payload to classify")

        payload = {
            "text": [
                "I would like to punch you.",
                "In hindsight, I do apologize for my previous statement"
            ]
        }

        resp = self._send_request(classifier_spec['port'], '/model/predict', payload)

        print("Text classification response", resp)

        # TODO: terminate containers
        print("Stopping compression service")
        compress_spec['service_obj'].remove()

        print("Stopping text classification service")
        classifier_spec['service_obj'].remove()

        return resp

    def run_workflow_a_persist(self, input_data):
        print("Starting persistant workflow for audio surveillance")

        # TODO: create required components or fetch existing
        print("Starting compression service")
        compress_spec = self.create_service_persist('compression')

        print("Starting text classification service")
        classifier_spec = self.create_service_persist('text_classification')

        # TODO: Send request to component in order one-by-one and transform result
        # as required for next component
        print("Sending payload to compress")

        payload = {"type": "gzip","data": input_data}

        resp = self._send_request(compress_spec['port'], '/compress', payload)

        print("Compression response", resp)

        print("Sending payload to classify")

        payload = {
            "text": [
                "I would like to punch you.",
                "In hindsight, I do apologize for my previous statement."
            ]
        }

        resp = self._send_request(classifier_spec['port'], '/model/predict', payload)

        print("Text classification response", resp)

        return resp