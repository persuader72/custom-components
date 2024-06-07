"""Contains sensors exposed by the Prism wallbox integration."""

from datetime import datetime
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .domain_data import DomainData
from .entity import PrismBaseEntity
from .entry_data import RuntimeEntryData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all sensors for this entry."""
    entry_data: RuntimeEntryData = DomainData.get(hass).get_entry_data(entry)
    _LOGGER.debug("async_setup_entry for sensors: %s", entry_data)
    sensors = [PrismSensor(entry_data, description) for description in SENSORS]
    async_add_entities(sensors)


class PrismSensorEntityDescription(SensorEntityDescription, frozen_or_thawed=True):
    """A class that describes prism binary sensor entities."""

    expire_after: float = 600
    topic: str = None


class PrismSensor(PrismBaseEntity, SensorEntity):
    """A Sensor for Prism wallbox devices."""

    entity_description: PrismSensorEntityDescription

    def __init__(
        self, entry_data: RuntimeEntryData, description: EntityDescription
    ) -> None:
        """Init Prism sensor."""
        super().__init__(entry_data, "sensor", description)
        self._unsubscribe = None

    async def _subscribe_topic(self):
        """Subscribe to mqtt topic."""
        _LOGGER.debug("_subscribe_topic: %s", self._topic)
        self._unsubscribe = await self.hass.components.mqtt.async_subscribe(
            self._topic, self.message_received
        )

    async def _unsubscribe_topic(self):
        """Unsubscribe to mqtt topic."""
        _LOGGER.debug("_unsubscribe_topic: %s", self._topic)
        if self._unsubscribe is not None:
            await self._unsubscribe()

    @callback
    def _value_is_expired(self, *_: datetime) -> None:
        """Triggered when value is expired."""
        _LOGGER.debug("_value_is_expired %s", self._topic)
        self._expiration_trigger = None
        self._attr_available = False
        self.async_write_ha_state()

    def _message_received(self, msg) -> None:
        """Update the sensor with the most recent event."""
        _LOGGER.debug("_message_received %s %s", self._topic, msg.payload)
        if self._expire_after is not None and self._expire_after > 0:
            # When self._expire_after is set, and we receive a message, assume
            # device is not expired since it has to be to receive the message
            self._attr_available = True
            # Reset old trigger
            if self._expiration_trigger:
                self._expiration_trigger()
            # Set new trigger
            self._expiration_trigger = async_call_later(
                self.hass, self._expire_after, self._value_is_expired
            )
        # Update native value
        if self.options is not None:
            try:
                self._attr_native_value = self.options[int(msg.payload) - 1]
            except IndexError:
                self._attr_native_value = None
        else:
            self._attr_native_value = msg.payload
        # Schedule update ha state
        self.schedule_update_ha_state()

    def message_received(self, msg) -> None:
        """Update the sensor with the most recent event."""
        self.hass.loop.call_soon_threadsafe(self._message_received, msg)

    async def async_added_to_hass(self) -> None:
        """Subscribe to mqtt."""
        _LOGGER.debug("async_added_to_hass")
        self._attr_available = False
        await self._subscribe_topic()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from mqtt."""
        _LOGGER.debug("called async_will_remove_from_hass fir %s", self.entity_id)
        await super().async_will_remove_from_hass()
        # Clean up expire triggers
        if self._expiration_trigger:
            self._expiration_trigger()
            self._expiration_trigger = None
            self._attr_available = True
        if self._unsubscribe is not None:
            await self._unsubscribe_topic()


SENSORS: tuple[PrismSensorEntityDescription, ...] = (
    PrismSensorEntityDescription(
        key="current_state",
        topic="1/state",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "waiting", "charging", "pause"],
        has_entity_name=True,
        translation_key="current_state",
    ),
    PrismSensorEntityDescription(
        key="power_grid_voltage",
        topic="1/volt",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="power_grid_voltage",
    ),
    PrismSensorEntityDescription(
        key="output_power",
        topic="1/w",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="output_power",
    ),
    PrismSensorEntityDescription(
        key="output_current",
        topic="1/amp",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="output_current",
    ),
    PrismSensorEntityDescription(
        key="output_car_current",
        topic="1/pilot",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="output_car_current",
    ),
    PrismSensorEntityDescription(
        key="current_set_by_user",
        topic="1/user_amp",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="current_set_by_user",
    ),
    PrismSensorEntityDescription(
        key="session_time",
        topic="1/session_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="session_time",
    ),
    PrismSensorEntityDescription(
        key="session_output_energy",
        topic="1/wh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="session_output_energy",
    ),
    PrismSensorEntityDescription(
        key="total_output_energy",
        topic="1/wh_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="total_output_energy",
    ),
    # FIXME: suspended is not 4 but 7
    PrismSensorEntityDescription(
        key="current_port_mode",
        topic="1/mode",
        device_class=SensorDeviceClass.ENUM,
        options=["solar", "normal", "paused", "suspended"],
        has_entity_name=True,
        translation_key="current_port_mode",
    ),
    PrismSensorEntityDescription(
        key="input_grid_power",
        topic="energy_data/power_grid",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        has_entity_name=True,
        translation_key="input_grid_power",
    ),
)
