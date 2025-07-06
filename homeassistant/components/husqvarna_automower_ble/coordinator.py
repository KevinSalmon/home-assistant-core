"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

import threading
from datetime import timedelta
from typing import TYPE_CHECKING

from automower_ble.mower import Mower
from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import HusqvarnaConfigEntry

SCAN_INTERVAL = timedelta(seconds=60)


type HusqvarnaConfigEntry = ConfigEntry[HusqvarnaCoordinator]


class HusqvarnaCoordinator(DataUpdateCoordinator[dict[str, str | int]]):
    """Class to manage fetching data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HusqvarnaConfigEntry,
        mower: Mower,
        address: str,
        channel_id: str,
        model: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.address = address
        self.channel_id = channel_id
        self.model = model
        self.mower = mower
        self.lock = threading.Lock()
        self.connection_allowed = True

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        LOGGER.debug("Shutdown")
        await super().async_shutdown()
        if self.mower.is_connected():
            await self.mower.disconnect()

    async def block_connection(self):
        self.connection_allowed = False
        if self.mower.is_connected():
            await self.mower.disconnect()
        await self.async_request_refresh()

    async def allow_connection(self):
        self.connection_allowed = True
        await self.async_request_refresh()

    async def async_set_value(self, protocol, key, **kwargs) -> None:
        if not self.connection_allowed:
            LOGGER.debug("async_set_value disabled")
            return

        await self._async_find_device()

        try:
            await self.mower.command(protocol, **kwargs)
        except BleakError as err:
            LOGGER.error(f"Error setting {protocol} to device: {err}")
            raise UpdateFailed("Error setting data to device") from err

        self.data[key] = next(iter(kwargs.values()))
        self.async_update_listeners()

    async def async_set_tasks(self, tasks) -> None:
        if not self.connection_allowed:
            LOGGER.debug("async_set_tasks disabled")
            return

        await self._async_find_device()

        try:
            await self.mower.command("StartTaskTransaction")
            await self.mower.command("DeleteAllTask")
            for task in tasks:
                await self.mower.command("AddTask",
                                         start=task['start'],
                                         duration=task['duration'],
                                         useOnSunday=task['useOnSunday'],
                                         unknown_1=task['unknown_1'],
                                         useOnMonday=task['useOnMonday'],
                                         useOnTuesday=task['useOnTuesday'],
                                         useOnWednesday=task['useOnWednesday'],
                                         useOnThursday=task['useOnThursday'],
                                         useOnFriday=task['useOnFriday'],
                                         useOnSaturday=task['useOnSaturday'],
                                         unknown_2=task['unknown_2']
                )
            await self.mower.command("CommitTaskTransaction")
        except BleakError as err:
            LOGGER.error(f"Error setting data to device: {err}")
            raise UpdateFailed("Error setting data to device") from err

        self.data["tasks"] = tasks
        self.async_update_listeners()

    async def _async_find_device(self):
        with self.lock:
            try:
                if self.mower.is_connected():
                    return
            except BleakError as err:
                raise UpdateFailed("Failed to connect") from err

            LOGGER.debug("Trying to reconnect")
            await close_stale_connections_by_address(self.address)

            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )

            try:
                if not await self.mower.connect(device):
                    raise UpdateFailed("Failed to connect")
            except BleakError as err:
                raise UpdateFailed("Failed to connect") from err

    async def _async_update_data(self) -> dict[str, str | int | bool]:
        """Poll the device."""

        LOGGER.debug("Polling device")

        if not self.connection_allowed:
            raise UpdateFailed("Polling device disabled")

        data: dict[str, str | int | bool] = {}  # TODO list

        await self._async_find_device()

        try:
            data["battery_level"] = await self.mower.command("GetBatteryLevel")
            data["mode"] = await self.mower.command("GetMode")
            # data["error"] = await self.mower.command("GetError")
            data["is_charging"] = True if await self.mower.command("IsCharging") == 1 else False
            # data["is_operator_logged_in"] = True if await self.mower.command("IsOperatorLoggedIn") == 1 else False
            data["remaining_charging_time"] = await self.mower.command("GetRemainingChargingTime")
            data["restriction_reason"] = await self.mower.command("GetRestrictionReason")
            data["startup_sequence_required"] = True if await self.mower.command("GetStartupSequenceRequired") == 1 else False

            data["cutting_height"] = await self.mower.command("GetCuttingHeight")
            # data["time"] = datetime.fromtimestamp(await self.mower.command("GetTime"), tz=timezone.utc).replace(tzinfo=tzlocal.get_localzone())

            # next_start_time = await self.mower.command("GetNextStartTime")
            # data["next_start_time"] = None if next_start_time in [None, 0] else datetime.fromtimestamp(next_start_time, timezone.utc).replace(tzinfo=tzlocal.get_localzone())

            data["number_of_tasks"] = await self.mower.command("GetNumberOfTasks") or 0
            data["tasks"] = []
            for taskId in range(data["number_of_tasks"]):
                task = await self.mower.command("GetTask", taskId=taskId)
                #task["start_date"] = datetime.fromtimestamp(task["start"], timezone.utc).replace(tzinfo=tzlocal.get_localzone())
                #task["end_date"] = task["start_date"] + timedelta(seconds=task["duration"])
                data["tasks"].append(task)

            # data["number_of_messages"] = await self.mower.command("GetNumberOfMessages") or 0
            # data["messages"] = []

            # for messageId in range(data["number_of_messages"]):
            #     message = await self.mower.command("GetMessage", messageId=messageId)
            #     if message is not None:
            #         severities = ["FATAL", "ERROR", "WARNING", "INFO", "DEBUG", "SW", "UNKNOWN"]
            #         data["messages"].append({
            #             "time": datetime.fromtimestamp(message.get("time", 0), timezone.utc).replace(tzinfo=tzlocal.get_localzone()),
            #             "code": ErrorCodes(message.get("code", 0)),
            #             "severity": severities[message.get("severity", 6)],
            #         })

            # override = await self.mower.command("GetOverride")
            # if override is None:
            #     override = {}
            # data["override_action"] = override.get("action")
            # data["override_start_time"] = None if override.get("startTime", 0) == 0 else datetime.fromtimestamp(override["startTime"], timezone.utc).replace(tzinfo=tzlocal.get_localzone())
            # data["override_duration"] = override.get("duration")

            all_statistics = await self.mower.command("GetAllStatistics")
            if all_statistics is None:
                all_statistics = {}
            data["cutting_blade_usage_time"] = all_statistics.get("cuttingBladeUsageTime")
            data["number_of_charging_cycles"] = all_statistics.get("numberOfChargingCycles")
            data["number_of_collisions"] = all_statistics.get("numberOfCollisions")
            data["total_charging_time"] = all_statistics.get("totalChargingTime")
            data["total_cutting_time"] = all_statistics.get("totalCuttingTime")
            data["total_running_time"] = all_statistics.get("totalRunningTime")
            data["total_searching_time"] = all_statistics.get("totalSearchingTime")

            data["activity"] = await self.mower.mower_activity()
            data["state"] = await self.mower.mower_state()

            LOGGER.debug(f"Data polled: {data}")

            if data["activity"] is None:
                raise UpdateFailed("Error getting activity from device")

            if data["state"] is None:
                raise UpdateFailed("Error getting state from device")

        except BleakError as err:
            LOGGER.error("Error getting data from device")
            raise UpdateFailed("Error getting data from device") from err

        return data
