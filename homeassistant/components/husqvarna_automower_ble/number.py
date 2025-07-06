"""Creates the number entities for the mower."""

import logging

from dataclasses import dataclass
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from typing import Callable, Optional

from .coordinator import HusqvarnaConfigEntry
from .entity import HusqvarnaAutomowerBleDescriptorEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class HusqvarnaNumberEntityDescription(NumberEntityDescription):
    set_value_fn: Optional[Callable[[float], None]] = None


NUMBER_DESCRIPTIONS = (
    HusqvarnaNumberEntityDescription(
        key="cutting_height",
        translation_key="cutting_height",
        device_class=NumberDeviceClass.DISTANCE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=9,
        native_step=1,
        native_unit_of_measurement="cm",
        set_value_fn=lambda coordinator, value: coordinator.async_set_value("SetCuttingHeight", "cutting_height", height=round(value)),
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
        HusqvarnaAutomowerBleNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
        if description.key in coordinator.data
    )


class HusqvarnaAutomowerBleNumber(HusqvarnaAutomowerBleDescriptorEntity, NumberEntity):
    """Representation of a number."""

    entity_description: HusqvarnaNumberEntityDescription

    @property
    def native_value(self) -> int:
        """Return the previously fetched value."""
        return self.coordinator.data[self.entity_description.key]

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_value_fn(self.coordinator, value)
