"""Creates the number entities for the mower."""

from dataclasses import dataclass
import logging
from typing import Any, Callable, Optional

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HusqvarnaConfigEntry
from .entity import HusqvarnaAutomowerBleDescriptorEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class HusqvarnaSwitchEntityDescription(SwitchEntityDescription):
    set_on_fn: Optional[Callable[[Any], None]] = None
    set_off_fn: Optional[Callable[[Any], None]] = None
    is_on_fn: Optional[Callable[[Any], bool]] = None


SWITCH_DESCRIPTIONS = (
    HusqvarnaSwitchEntityDescription(
        key="allow_connection",
        translation_key="allow_connection",
        device_class=SwitchDeviceClass.SWITCH,
        set_on_fn=lambda coordinator: coordinator.allow_connection(),
        set_off_fn=lambda coordinator: coordinator.allow_connection(),
        is_on_fn=lambda coordinator: coordinator.connection_allowed,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HusqvarnaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Husqvarna Automower Ble number based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        HusqvarnaAutomowerBleSwitch(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    )


class HusqvarnaAutomowerBleSwitch(HusqvarnaAutomowerBleDescriptorEntity, SwitchEntity):
    """Representation of a number."""

    entity_description: SwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on if heat mode is enabled."""
        await self.entity_description.set_on_fn(self.coordinator)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set_off_fn(self.coordinator)

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator)
