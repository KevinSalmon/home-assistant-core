"""Creates a calendar entity for the mower."""

from datetime import datetime, timedelta, time
import logging
import homeassistant.util.dt as dt_util
import voluptuous as vol

import logging

from dateutil.rrule import rrulestr

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HusqvarnaConfigEntry
from .entity import HusqvarnaAutomowerBleDescriptorEntity

from homeassistant.components.calendar import CalendarEntity, CalendarEvent, CalendarEntityDescription, CalendarEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import HusqvarnaConfigEntry


_LOGGER = logging.getLogger(__name__)

CALENDAR_DESCRIPTIONS = (
    CalendarEntityDescription(
        key="tasks",
        translation_key="tasks",
        entity_category=EntityCategory.CONFIG
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
        HusqvarnaAutomowerBleCalendar(coordinator, description)
        for description in CALENDAR_DESCRIPTIONS
        if description.key in coordinator.data
    )


class HusqvarnaAutomowerBleCalendar(HusqvarnaAutomowerBleDescriptorEntity, CalendarEntity):
    """Representation of a Calendar."""

    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT
        | CalendarEntityFeature.DELETE_EVENT
        | CalendarEntityFeature.UPDATE_EVENT
    )

    entity_description: CalendarEntityDescription

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:

        event_list = []
        for taskId, task in enumerate(self.coordinator.data["tasks"]):
            day_list = []
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if task[f"useOn{day.capitalize()}"] == 1:
                    day_list.append(day.upper()[0:2])
            rrule = f"FREQ=WEEKLY;BYDAY={','.join(day_list)}"

            start_time = time(task["start"] // 3600, (task["start"] % 3600) // 60, task["start"] % 60)

            dtstart = dt_util.as_utc(datetime.combine(start_date.date(), start_time))
            rule = rrulestr(rrule, dtstart=dtstart)
            occurrences = rule.between(start_date, end_date, inc=True)

            for i, occ in enumerate(occurrences):
                event = CalendarEvent(
                    summary=f"Programme {taskId + 1}",
                    start=occ,
                    end=occ + timedelta(seconds=task["duration"]),
                    description="",
                    uid=taskId,
                    rrule=rrule,
                    recurrence_id=occ.strftime("%Y%m%dT%H%M%S"),
                )
                event_list.append(event)

        _LOGGER.warning(f"event_list: {event_list}")

        return event_list

    async def async_create_event(self, **kwargs) -> None:
        """Add a new event to calendar."""
        tasks = self.coordinator.data["tasks"]
        tasks.append(self.to_husqvarna_format(kwargs))
        await self.coordinator.async_set_tasks(tasks)

    async def async_update_event(
        self,
        uid: str,
        event: dict[str],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Update an existing event in calendar."""
        tasks = self.coordinator.data["tasks"]
        tasks[int(uid)] = self.to_husqvarna_format(event)
        await self.coordinator.async_set_tasks(tasks)

    def to_husqvarna_format(self, event):
        """Convert event to Husqvarna task format."""
        if "rrule" not in event:
            raise vol.Invalid("Only reccuring events are allowed")
        if "WEEKLY" not in event["rrule"]:
            raise vol.Invalid("Please select weekly")
        if "BYDAY" not in event["rrule"]:
            raise vol.Invalid("Please select day(s)")

        rr_list = event["rrule"].split(";")
        days = rr_list[1].lstrip("BYDAY=")
        day_list = days.split(",")

        start_time = event["dtstart"].hour * 3600 + event["dtstart"].minute * 60 + event["dtstart"].second
        end_time = event["dtend"].hour * 3600 + event["dtend"].minute * 60 + event["dtend"].second

        task = {
            "start": start_time,
            "duration": end_time - start_time,
            "unknown_1": 0,
            "unknown_2": 0,
        }
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            task[f"useOn{day.capitalize()}"] = 1 if day.upper()[0:2] in day_list else 0
        return task

    async def async_delete_event(
            self,
            uid: str,
            recurrence_id: str | None = None,
            recurrence_range: str | None = None,
        ) -> None:
        """Delete an existing event in calendar."""
        tasks = self.coordinator.data["tasks"]
        # TODO Always at least one task (required by Husqvarna)
        tasks.pop(int(uid))
        await self.coordinator.async_set_tasks(tasks)
