# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

import ops.testing
from ops.model import ActiveStatus
from ops.pebble import ServiceInfo, ServiceStartup, ServiceStatus
from ops.testing import Harness

from charm import Oai5GAUSFOperatorCharm


class TestCharm(unittest.TestCase):
    @patch(
        "charm.KubernetesServicePatch",
        lambda charm, ports: None,
    )
    def setUp(self):
        ops.testing.SIMULATE_CAN_CONNECT = True
        self.model_name = "whatever"
        self.addCleanup(setattr, ops.testing, "SIMULATE_CAN_CONNECT", False)
        self.harness = Harness(Oai5GAUSFOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.set_model_name(name=self.model_name)
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

    def _create_udm_relation_with_valid_data(self):
        relation_id = self.harness.add_relation("fiveg-udm", "udm")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="udm/0")

        udm_ipv4_address = "1.2.3.4"
        udm_port = "81"
        udm_api_version = "v1"
        udm_fqdn = "udm.example.com"
        key_values = {
            "udm_ipv4_address": udm_ipv4_address,
            "udm_port": udm_port,
            "udm_fqdn": udm_fqdn,
            "udm_api_version": udm_api_version,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="udm", key_values=key_values
        )
        return udm_ipv4_address, udm_port, udm_api_version, udm_fqdn

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

        (
            udm_ipv4_address,
            udm_port,
            udm_api_version,
            udm_fqdn,
        ) = self._create_udm_relation_with_valid_data()

        self.harness.update_config(key_values={"sbiIfName": "eth0"})

        mock_push.assert_called_with(
            path="/openair-ausf/etc/ausf.conf",
            source="## AUSF configuration file\n"
            "AUSF =\n"
            "{\n"
            "  INSTANCE_ID = 0;\n"
            '  PID_DIRECTORY = "/var/run";\n'
            '  AUSF_NAME = "OAI_AUSF";\n\n'
            "  INTERFACES:{\n"
            "    # AUSF binded interface for SBI interface (e.g., communication with AMF, UDM)\n"  # noqa: E501, W505
            "    SBI:{\n"
            '        INTERFACE_NAME = "eth0";      # YOUR NETWORK CONFIG HERE\n'
            '        IPV4_ADDRESS   = "read";\n'
            "        PORT           = 80;           # YOUR NETWORK CONFIG HERE (default: 80)\n"  # noqa: E501, W505
            '        API_VERSION    = "v1";  # YOUR API VERSION FOR UDM CONFIG HERE\n'
            "        HTTP2_PORT     = 9090;     # YOUR NETWORK CONFIG HERE\n"
            "    };\n"
            "  };\n\n"
            "  # SUPPORT FEATURES\n"
            "  SUPPORT_FEATURES:{\n"
            '    # STRING, {"yes", "no"},\n'
            '    USE_FQDN_DNS = "yes";    # Set to yes if AUSF will relying on a DNS to resolve UDM\'s FQDN\n'  # noqa: E501, W505
            '    USE_HTTP2    = "no";                 # Set to yes to enable HTTP2 for AMF server\n'  # noqa: E501, W505
            "    REGISTER_NRF = \"no\";    # Set to 'yes' if AUSF resgisters to an NRF\n"
            "  }\n\n"
            "  # UDM Information\n"
            "  UDM:{\n"
            f'    IPV4_ADDRESS   = "{ udm_ipv4_address }";  # YOUR NETWORK CONFIG HERE\n'
            f"    PORT           = { udm_port };          # YOUR NETWORK CONFIG HERE  (default: 80)\n"  # noqa: E501, W505
            f'    API_VERSION    = "{ udm_api_version }";  # YOUR API VERSION FOR UDM CONFIG HERE\n'  # noqa: E501, W505
            f'    FQDN           = "{ udm_fqdn }"         # YOUR UDM FQDN CONFIG HERE\n'
            "  };\n\n"
            "  NRF :\n"
            "  {\n"
            f'    IPV4_ADDRESS = "{ nrf_ipv4_address }";  # YOUR NRF CONFIG HERE\n'
            f"    PORT         = { nrf_port };            # YOUR NRF CONFIG HERE (default: 80)\n"  # noqa: E501, W505
            f'    API_VERSION  = "{ nrf_api_version }";   # YOUR NRF API VERSION HERE\n'
            f'    FQDN = "{ nrf_fqdn }";\n'
            "  };\n"
            "};",
        )

    @patch("ops.model.Container.push")
    def test_given_nrf_and_db_relation_are_set_when_config_changed_then_pebble_plan_is_created(  # noqa: E501
        self, _
    ):
        self.harness.set_can_connect(container="ausf", val=True)
        self._create_nrf_relation_with_valid_data()
        self._create_udm_relation_with_valid_data()

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

    @patch("ops.model.Container.get_service")
    def test_given_unit_is_leader_when_ausf_relation_joined_then_ausf_relation_data_is_set(
        self, patch_get_service
    ):
        self.harness.set_leader(True)
        self.harness.set_can_connect(container="ausf", val=True)
        patch_get_service.return_value = ServiceInfo(
            name="ausf",
            current=ServiceStatus.ACTIVE,
            startup=ServiceStartup.ENABLED,
        )

        relation_id = self.harness.add_relation(relation_name="fiveg-ausf", remote_app="amf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="amf/0")

        relation_data = self.harness.get_relation_data(
            relation_id=relation_id, app_or_unit=self.harness.model.app.name
        )

        assert relation_data["ausf_ipv4_address"] == "127.0.0.1"
        assert relation_data["ausf_fqdn"] == f"oai-5g-ausf.{self.model_name}.svc.cluster.local"
        assert relation_data["ausf_port"] == "80"
        assert relation_data["ausf_api_version"] == "v1"
