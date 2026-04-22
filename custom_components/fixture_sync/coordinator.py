"""Coordinator that fetches fixtures and creates calendar events."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiohttp
from homeassistant.components.calendar import CalendarEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CALENDAR_ENTITY,
    CONF_COMPETITION,
    CONF_EVENT_HOURS,
    CONF_TEAM,
    FIXTUREDOWNLOAD_URL,
)

_LOGGER = logging.getLogger(__name__)


class FixtureSyncCoordinator:
    """Fetch fixtures on a schedule and create calendar events for matches."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.competition: str = entry.data[CONF_COMPETITION]
        self.team: str = entry.data[CONF_TEAM]
        self.calendar_entity_id: str = entry.data[CONF_CALENDAR_ENTITY]
        self.event_hours: int = entry.data.get(CONF_EVENT_HOURS, 2)

    async def async_sync(self) -> None:
        """Fetch fixtures and upsert calendar events."""
        try:
            fixtures = await self._fetch_fixtures()
        except Exception as err:
            _LOGGER.error("Failed to fetch fixtures for %s: %s", self.competition, err)
            return

        matches = self._filter_future_team_matches(fixtures)
        if not matches:
            _LOGGER.info("No future %s matches for %s", self.competition, self.team)
            return

        existing = await self._existing_events(matches)
        created = 0
        for match in matches:
            start = match["start"]
            end = match["end"]
            summary = match["summary"]
            key = (summary, start.isoformat())
            if key in existing:
                continue
            await self.hass.services.async_call(
                "calendar",
                "create_event",
                {
                    "entity_id": self.calendar_entity_id,
                    "summary": summary,
                    "description": match["description"],
                    "location": match["location"],
                    "start_date_time": start.isoformat(),
                    "end_date_time": end.isoformat(),
                },
                blocking=True,
            )
            created += 1

        _LOGGER.info(
            "%s: %d match(es) found, %d new created in %s",
            self.team, len(matches), created, self.calendar_entity_id,
        )

    async def _fetch_fixtures(self) -> list[dict]:
        url = FIXTUREDOWNLOAD_URL.format(competition=self.competition)
        session = async_get_clientsession(self.hass)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    def _filter_future_team_matches(self, fixtures: list[dict]) -> list[dict]:
        now = datetime.now(timezone.utc)
        needle = self.team.lower()
        out: list[dict] = []
        for m in fixtures:
            home = m.get("HomeTeam", "") or ""
            away = m.get("AwayTeam", "") or ""
            if needle not in home.lower() and needle not in away.lower():
                continue
            date_utc = m.get("DateUtc")
            if not date_utc:
                continue
            try:
                start = datetime.fromisoformat(date_utc.replace("Z", "+00:00"))
            except ValueError:
                continue
            if start <= now:
                continue
            end = start + timedelta(hours=self.event_hours)
            out.append({
                "start": start,
                "end": end,
                "summary": f"{home} vs {away}",
                "location": m.get("Location") or "",
                "description": f"{self.competition} · {m.get('Location') or ''}".strip(" ·"),
            })
        return out

    async def _existing_events(self, matches: list[dict]) -> set[tuple[str, str]]:
        """Return set of (summary, start_iso) for events already in the calendar."""
        entity = self._get_calendar_entity()
        if entity is None:
            _LOGGER.warning("Calendar entity %s not found", self.calendar_entity_id)
            return set()
        earliest = min(m["start"] for m in matches)
        latest = max(m["end"] for m in matches)
        try:
            events = await entity.async_get_events(self.hass, earliest, latest)
        except Exception as err:
            _LOGGER.warning("Could not read calendar events (%s); proceeding", err)
            return set()
        result: set[tuple[str, str]] = set()
        for ev in events:
            start = ev.start
            if hasattr(start, "isoformat"):
                start_iso = start.isoformat()
            else:
                start_iso = str(start)
            result.add((ev.summary or "", start_iso))
        return result

    def _get_calendar_entity(self) -> CalendarEntity | None:
        component = self.hass.data.get("calendar")
        if component is None:
            return None
        return component.get_entity(self.calendar_entity_id)
