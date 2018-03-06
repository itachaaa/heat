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

import mock

from openstack import exceptions

from heat.engine.clients.os import openstacksdk
from heat.tests import common
from heat.tests import utils


class OpenStackSDKPluginTest(common.HeatTestCase):

    @mock.patch('openstack.connection.Connection')
    def test_create(self, mock_connection):
        context = utils.dummy_context()
        plugin = context.clients.client_plugin('openstack')
        client = plugin.client()
        self.assertIsNotNone(client.network.segments)


class SegmentConstraintTest(common.HeatTestCase):

    def setUp(self):
        super(SegmentConstraintTest, self).setUp()
        self.ctx = utils.dummy_context()
        self.mock_find_segment = mock.Mock()
        self.ctx.clients.client_plugin(
            'openstack').find_network_segment = self.mock_find_segment
        self.constraint = openstacksdk.SegmentConstraint()

    def test_validation(self):
        self.mock_find_segment.side_effect = [
            "seg1", exceptions.ResourceNotFound(),
            exceptions.DuplicateResource()]
        self.assertTrue(self.constraint.validate("foo", self.ctx))
        self.assertFalse(self.constraint.validate("bar", self.ctx))
        self.assertFalse(self.constraint.validate("baz", self.ctx))
