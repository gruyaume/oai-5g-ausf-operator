# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

import ops.testing
from ops.model import ActiveStatus
from ops.testing import Harness

from charm import Oai5GAUSFOperatorCharm


class TestCharm(unittest.TestCase):
    @patch(
        "charm.KubernetesServicePatch",
        lambda charm, ports: None,
    )
    def setUp(self):
        ops.testing.SIMULATE_CAN_CONNECT = True
        self.addCleanup(setattr, ops.testing, "SIMULATE_CAN_CONNECT", False)
        self.harness = Harness(Oai5GAUSFOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def _create_nrf_relation_with_valid_data(self):
        relation_id = self.harness.add_relation("fiveg-nrf", "nrf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="nrf/0")

        nrf_ipv4_address = "1.2.3.4"
        nrf_port = "81"
        nrf_api_version = "v1"
        nrf_fqdn = "nrf.example.com"
        key_values = {
            "nrf_ipv4_address": nrf_ipv4_address,
            "nrf_port": nrf_port,
            "nrf_fqdn": nrf_fqdn,
            "nrf_api_version": nrf_api_version,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="nrf", key_values=key_values
        )
        return nrf_ipv4_address, nrf_port, nrf_api_version, nrf_fqdn

    @patch("ops.model.Container.push")
    def test_given_nrf_relation_contains_nrf_info_when_nrf_relation_joined_then_config_file_is_pushed(  # noqa: E501
        self, mock_push
    ):
        self.harness.set_can_connect(container="ausf", val=True)
        (
            nrf_ipv4_address,
            nrf_port,
            nrf_api_version,
            nrf_fqdn,
        ) = self._create_nrf_relation_with_valid_data()

        self.harness.update_config(key_values={"sbiIfName": "eth0"})

        mock_push.assert_called_with(
            path="/openair-ausf/etc/ausf.conf",
            source="",
        )

    @patch("ops.model.Container.push")
    def test_given_nrf_and_db_relation_are_set_when_config_changed_then_pebble_plan_is_created(  # noqa: E501
        self, _
    ):
        self.harness.set_can_connect(container="ausf", val=True)
        self._create_nrf_relation_with_valid_data()

        self.harness.update_config({"sbiIfName": "eth0"})

        expected_plan = {
            "services": {
                "ausf": {
                    "override": "replace",
                    "summary": "ausf",
                    "command": "/openair-ausf/bin/oai_ausf -c /openair-ausf/etc/ausf.conf -o",
                    "startup": "enabled",
                }
            },
        }
        self.harness.container_pebble_ready("ausf")
        updated_plan = self.harness.get_container_pebble_plan("ausf").to_dict()
        self.assertEqual(expected_plan, updated_plan)
        service = self.harness.model.unit.get_container("ausf").get_service("ausf")
        self.assertTrue(service.is_running())
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
