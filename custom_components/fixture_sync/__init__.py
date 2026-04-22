"""Fixture Sync integration: mirror football fixtures into an HA calendar."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SYNC_INTERVAL_HOURS
from .coordinator import FixtureSyncCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Fixture Sync config entry."""
    coordinator = FixtureSyncCoordinator(hass, entry)
    await coordinator.async_sync()

    cancel = async_track_time_interval(
        hass, lambda _now: hass.async_create_task(coordinator.async_sync()),
        timedelta(hours=SYNC_INTERVAL_HOURS),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "cancel": cancel,
    }

    async def _handle_sync_now(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        entries = hass.data[DOMAIN]
        targets = [entries[entry_id]] if entry_id else list(entries.values())
        for item in targets:
            await item["coordinator"].async_sync()

    if not hass.services.has_service(DOMAIN, "sync_now"):
        hass.services.async_register(DOMAIN, "sync_now", _handle_sync_now)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data and data.get("cancel"):
        data["cancel"]()
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "sync_now")
    return True
