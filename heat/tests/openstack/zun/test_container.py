#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import copy
import mock
import six

from oslo_config import cfg
from zunclient import exceptions as zc_exc

from heat.common import exception
from heat.common import template_format
from heat.engine.resources.openstack.zun import container
from heat.engine import scheduler
from heat.engine import template
from heat.tests import common
from heat.tests import utils

zun_template = '''
heat_template_version: 2017-09-01

resources:
  test_container:
    type: OS::Zun::Container
    properties:
      name: test_container
      image: "cirros:latest"
      command: sleep 10000
      cpu: 0.1
      memory: 100
      environment:
        myenv: foo
      workdir: /testdir
      labels:
        mylabel: bar
      image_pull_policy: always
      restart_policy: on-failure:2
      interactive: false
      image_driver: docker
      hints:
        hintkey: hintval
      hostname: myhost
      security_groups:
        - my_seg
      mounts:
        - volume_size: 1
          mount_path: /data
        - volume_id: 6ec29ba3-bf2c-4276-a88e-3670ea5abc80
          mount_path: /data2
'''


class ZunContainerTest(common.HeatTestCase):

    def setUp(self):
        super(ZunContainerTest, self).setUp()

        self.resource_id = '12345'
        self.fake_name = 'test_container'
        self.fake_image = 'cirros:latest'
        self.fake_command = 'sleep 10000'
        self.fake_cpu = 0.1
        self.fake_memory = 100
        self.fake_env = {'myenv': 'foo'}
        self.fake_workdir = '/testdir'
        self.fake_labels = {'mylabel': 'bar'}
        self.fake_image_policy = 'always'
        self.fake_restart_policy = {'MaximumRetryCount': '2',
                                    'Name': 'on-failure'}
        self.fake_interactive = False
        self.fake_image_driver = 'docker'
        self.fake_hints = {'hintkey': 'hintval'}
        self.fake_hostname = 'myhost'
        self.fake_security_groups = ['my_seg']
        self.fake_mounts = [
            {'volume_id': None, 'volume_size': 1, 'mount_path': '/data'},
            {'volume_id': '6ec29ba3-bf2c-4276-a88e-3670ea5abc80',
             'volume_size': None, 'mount_path': '/data2'}]
        self.fake_mounts_args = [
            {'size': 1, 'destination': '/data'},
            {'source': '6ec29ba3-bf2c-4276-a88e-3670ea5abc80',
             'destination': '/data2'}]

        self.fake_network_id = '9c11d847-99ce-4a83-82da-9827362a68e8'
        self.fake_network_name = 'private'
        self.fake_networks = {
            'networks': [
                {
                    'id': self.fake_network_id,
                    'name': self.fake_network_name,
                }
            ]
        }
        self.fake_address = {
            'version': 4,
            'addr': '10.0.0.12',
            'port': 'ab5c12d8-f414-48a3-b765-8ce34a6714d2'
        }
        self.fake_addresses = {
            self.fake_network_id: [self.fake_address]
        }
        self.fake_extended_addresses = {
            self.fake_network_id: [self.fake_address],
            self.fake_network_name: [self.fake_address],
        }

        t = template_format.parse(zun_template)
        self.stack = utils.parse_stack(t)
        resource_defns = self.stack.t.resource_definitions(self.stack)
        self.rsrc_defn = resource_defns[self.fake_name]
        self.client = mock.Mock()
        self.patchobject(container.Container, 'client',
                         return_value=self.client)
        self.neutron_client = mock.Mock()
        self.patchobject(container.Container, 'neutron',
                         return_value=self.neutron_client)
        self.stub_VolumeConstraint_validate()

    def _mock_get_client(self):
        value = mock.MagicMock()
        value.name = self.fake_name
        value.image = self.fake_image
        value.command = self.fake_command
        value.cpu = self.fake_cpu
        value.memory = self.fake_memory
        value.environment = self.fake_env
        value.workdir = self.fake_workdir
        value.labels = self.fake_labels
        value.image_pull_policy = self.fake_image_policy
        value.restart_policy = self.fake_restart_policy
        value.interactive = self.fake_interactive
        value.image_driver = self.fake_image_driver
        value.hints = self.fake_hints
        value.hostname = self.fake_hostname
        value.security_groups = self.fake_security_groups
        value.addresses = self.fake_addresses
        value.to_dict.return_value = value.__dict__

        self.client.containers.get.return_value = value

    def _create_resource(self, name, snippet, stack, status='Running'):
        value = mock.MagicMock(uuid=self.resource_id)
        self.client.containers.run.return_value = value
        get_rv = mock.MagicMock(status=status)
        self.client.containers.get.return_value = get_rv
        c = container.Container(name, snippet, stack)
        return c

    def test_create(self):
        c = self._create_resource('container', self.rsrc_defn,
                                  self.stack)
        # validate the properties
        self.assertEqual(
            self.fake_name,
            c.properties.get(container.Container.NAME))
        self.assertEqual(
            self.fake_image,
            c.properties.get(container.Container.IMAGE))
        self.assertEqual(
            self.fake_command,
            c.properties.get(container.Container.COMMAND))
        self.assertEqual(
            self.fake_cpu,
            c.properties.get(container.Container.CPU))
        self.assertEqual(
            self.fake_memory,
            c.properties.get(container.Container.MEMORY))
        self.assertEqual(
            self.fake_env,
            c.properties.get(container.Container.ENVIRONMENT))
        self.assertEqual(
            self.fake_workdir,
            c.properties.get(container.Container.WORKDIR))
        self.assertEqual(
            self.fake_labels,
            c.properties.get(container.Container.LABELS))
        self.assertEqual(
            self.fake_image_policy,
            c.properties.get(container.Container.IMAGE_PULL_POLICY))
        self.assertEqual(
            'on-failure:2',
            c.properties.get(container.Container.RESTART_POLICY))
        self.assertEqual(
            self.fake_interactive,
            c.properties.get(container.Container.INTERACTIVE))
        self.assertEqual(
            self.fake_image_driver,
            c.properties.get(container.Container.IMAGE_DRIVER))
        self.assertEqual(
            self.fake_hints,
            c.properties.get(container.Container.HINTS))
        self.assertEqual(
            self.fake_hostname,
            c.properties.get(container.Container.HOSTNAME))
        self.assertEqual(
            self.fake_security_groups,
            c.properties.get(container.Container.SECURITY_GROUPS))
        self.assertEqual(
            self.fake_mounts,
            c.properties.get(container.Container.MOUNTS))

        scheduler.TaskRunner(c.create)()
        self.assertEqual(self.resource_id, c.resource_id)
        self.assertEqual((c.CREATE, c.COMPLETE), c.state)
        self.assertEqual('containers', c.entity)
        self.client.containers.run.assert_called_once_with(
            name=self.fake_name,
            image=self.fake_image,
            command=self.fake_command,
            cpu=self.fake_cpu,
            memory=self.fake_memory,
            environment=self.fake_env,
            workdir=self.fake_workdir,
            labels=self.fake_labels,
            image_pull_policy=self.fake_image_policy,
            restart_policy=self.fake_restart_policy,
            interactive=self.fake_interactive,
            image_driver=self.fake_image_driver,
            hints=self.fake_hints,
            hostname=self.fake_hostname,
            security_groups=self.fake_security_groups,
            mounts=self.fake_mounts_args,
        )

    def test_container_create_failed(self):
        cfg.CONF.set_override('action_retry_limit', 0)
        c = self._create_resource('container', self.rsrc_defn, self.stack,
                                  status='Error')
        exc = self.assertRaises(
            exception.ResourceFailure,
            scheduler.TaskRunner(c.create))
        self.assertEqual((c.CREATE, c.FAILED), c.state)
        self.assertIn("Error in creating container ", six.text_type(exc))

    def test_container_create_unknown_status(self):
        c = self._create_resource('container', self.rsrc_defn, self.stack,
                                  status='FOO')
        exc = self.assertRaises(
            exception.ResourceFailure,
            scheduler.TaskRunner(c.create))
        self.assertEqual((c.CREATE, c.FAILED), c.state)
        self.assertIn("Unknown status Container", six.text_type(exc))

    def test_container_update(self):
        c = self._create_resource('container', self.rsrc_defn, self.stack)
        scheduler.TaskRunner(c.create)()
        t = template_format.parse(zun_template)
        new_t = copy.deepcopy(t)
        new_t['resources'][self.fake_name]['properties']['name'] = \
            'fake-container'
        new_t['resources'][self.fake_name]['properties']['cpu'] = 10
        new_t['resources'][self.fake_name]['properties']['memory'] = 10
        rsrc_defns = template.Template(new_t).resource_definitions(self.stack)
        new_c = rsrc_defns[self.fake_name]
        scheduler.TaskRunner(c.update, new_c)()
        self.client.containers.update.assert_called_once_with(
            self.resource_id, cpu=10, memory=10)
        self.client.containers.rename.assert_called_once_with(
            self.resource_id, name='fake-container')
        self.assertEqual((c.UPDATE, c.COMPLETE), c.state)

    def test_container_delete(self):
        c = self._create_resource('container', self.rsrc_defn, self.stack)
        scheduler.TaskRunner(c.create)()
        self.patchobject(self.client.containers, 'get',
                         side_effect=[c, zc_exc.NotFound('Not Found')])
        scheduler.TaskRunner(c.delete)()
        self.assertEqual((c.DELETE, c.COMPLETE), c.state)
        self.client.containers.delete.assert_called_once_with(
            c.resource_id, stop=True)

    def test_container_delete_not_found(self):
        c = self._create_resource('container', self.rsrc_defn, self.stack)
        scheduler.TaskRunner(c.create)()
        c.client_plugin = mock.MagicMock()
        self.client.containers.delete.side_effect = Exception('Not Found')
        scheduler.TaskRunner(c.delete)()
        self.assertEqual((c.DELETE, c.COMPLETE), c.state)
        self.client.containers.delete.assert_called_once_with(
            c.resource_id, stop=True)
        mock_ignore_not_found = c.client_plugin.return_value.ignore_not_found
        self.assertEqual(1, mock_ignore_not_found.call_count)

    def test_container_get_live_state(self):
        c = self._create_resource('container', self.rsrc_defn, self.stack)
        scheduler.TaskRunner(c.create)()
        self._mock_get_client()
        reality = c.get_live_state(c.properties)
        self.assertEqual(
            {
                container.Container.NAME: self.fake_name,
                container.Container.CPU: self.fake_cpu,
                container.Container.MEMORY: self.fake_memory,
            }, reality)

    def test_resolve_attributes(self):
        self.neutron_client.list_networks.return_value = self.fake_networks
        c = self._create_resource('container', self.rsrc_defn, self.stack)
        scheduler.TaskRunner(c.create)()
        self._mock_get_client()
        self.assertEqual(
            self.fake_name,
            c._resolve_attribute(container.Container.NAME))
        self.assertEqual(
            self.fake_extended_addresses,
            c._resolve_attribute(container.Container.ADDRESSES))

    def test_resolve_attributes_duplicate_net_name(self):
        self.neutron_client.list_networks.return_value = {
            'networks': [
                {'id': 'fake_net_id', 'name': 'test'},
                {'id': 'fake_net_id2', 'name': 'test'},
            ]
        }
        self.fake_addresses = {
            'fake_net_id': [{'addr': '10.0.0.12'}],
            'fake_net_id2': [{'addr': '10.100.0.12'}],
        }
        self.fake_extended_addresses = {
            'fake_net_id': [{'addr': '10.0.0.12'}],
            'fake_net_id2': [{'addr': '10.100.0.12'}],
            'test': [{'addr': '10.0.0.12'}, {'addr': '10.100.0.12'}],
        }
        c = self._create_resource('container', self.rsrc_defn, self.stack)
        scheduler.TaskRunner(c.create)()
        self._mock_get_client()
        self._assert_addresses(
            self.fake_extended_addresses,
            c._resolve_attribute(container.Container.ADDRESSES))

    def _assert_addresses(self, expected, actual):
        matched = True
        if len(expected) != len(actual):
            matched = False
        for key in expected:
            if key not in actual:
                matched = False
                break
            list1 = expected[key]
            list1 = sorted(list1, key=lambda x: sorted(x.values()))
            list2 = actual[key]
            list2 = sorted(list2, key=lambda x: sorted(x.values()))
            if list1 != list2:
                matched = False
                break

        if not matched:
            raise AssertionError(
                'Addresses is unmatched:\n reference = ' + str(expected) +
                '\nactual = ' + str(actual))
