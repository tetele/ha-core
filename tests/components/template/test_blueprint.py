"""Test built-in blueprints."""

from collections.abc import Iterator
import contextlib
from os import PathLike
import pathlib
from unittest.mock import patch

import pytest

from homeassistant.components import template
from homeassistant.components.blueprint import (
    BLUEPRINT_SCHEMA,
    Blueprint,
    DomainBlueprints,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml

from tests.common import MockConfigEntry

BUILTIN_BLUEPRINT_FOLDER = pathlib.Path(template.__file__).parent / "blueprints"


@contextlib.contextmanager
def patch_blueprint(
    blueprint_path: str, data_path: str | PathLike[str]
) -> Iterator[None]:
    """Patch blueprint loading from a different source."""
    orig_load = DomainBlueprints._load_blueprint

    @callback
    def mock_load_blueprint(self, path):
        if path != blueprint_path:
            pytest.fail(f"Unexpected blueprint {path}")
            return orig_load(self, path)

        return Blueprint(
            yaml.load_yaml(data_path),
            expected_domain=self.domain,
            path=path,
            schema=BLUEPRINT_SCHEMA,
        )

    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints._load_blueprint",
        mock_load_blueprint,
    ):
        yield


async def test_inverted_binary_sensor(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test inverted binary sensor blueprint."""
    config_entry = MockConfigEntry(domain="fake_integration", data={})
    config_entry.mock_state(hass, ConfigEntryState.LOADED)
    config_entry.add_to_hass(hass)

    hass.states.async_set("binary_sensor.foo", "on", {"friendly_name": "Foo"})
    hass.states.async_set("binary_sensor.bar", "off", {"friendly_name": "Bar"})

    with patch_blueprint(
        "inverted_binary_sensor.yaml",
        BUILTIN_BLUEPRINT_FOLDER / "inverted_binary_sensor.yaml",
    ):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": [
                    {
                        "use_blueprint": {
                            "path": "inverted_binary_sensor.yaml",
                            "input": {"original_entity": "binary_sensor.foo"},
                        },
                        "name": "Inverted foo",
                    },
                    {
                        "use_blueprint": {
                            "path": "inverted_binary_sensor.yaml",
                            "input": {"original_entity": "binary_sensor.bar"},
                        },
                        "name": "Inverted bar",
                    },
                ]
            },
        )

    hass.states.async_set("binary_sensor.foo", "off", {"friendly_name": "Foo"})
    hass.states.async_set("binary_sensor.bar", "on", {"friendly_name": "Bar"})
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.foo").state == "off"
    assert hass.states.get("binary_sensor.bar").state == "on"

    inverted_foo = hass.states.get("binary_sensor.inverted_foo")
    assert inverted_foo
    assert inverted_foo.state == "on"

    inverted_bar = hass.states.get("binary_sensor.inverted_bar")
    assert inverted_bar
    assert inverted_bar.state == "off"
