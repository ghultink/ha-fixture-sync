# Fixture Sync for Home Assistant

Mirror football fixtures from [fixturedownload.com](https://fixturedownload.com/) into a Home Assistant calendar. Every match becomes a calendar event, so you can trigger automations with the built-in `calendar` trigger (event `start` / `end`).

## Why

`fixturedownload.com` publishes free, no-key JSON feeds for most major competitions. Point this integration at a competition + team + calendar entity, and your automations can react to kickoff and final whistle — no paid API, no scraping.

## Install (via HACS)

1. **HACS → Integrations → ⋮ → Custom repositories.**
2. Repository: `https://github.com/ghultink/ha-fixture-sync`, category: `Integration`.
3. Install *Fixture Sync* and restart Home Assistant.
4. **Settings → Devices & services → Add integration → Fixture Sync.**

## Configure

| Field | Example |
|---|---|
| Competition slug | `la-liga-2025` |
| Team | `Real Madrid` |
| Calendar entity | `calendar.real_madrid` |
| Event duration (hours) | `2` |

The slug is the trailing part of the feed URL, e.g. `la-liga-2025` for `https://fixturedownload.com/feed/json/la-liga-2025`.

Team is matched case-insensitively as a substring against each fixture's `HomeTeam` / `AwayTeam`.

The integration syncs once on startup and then every 24 hours. Trigger manually with the `fixture_sync.sync_now` service.

## Example automation

```yaml
alias: Real Madrid lampje tijdens wedstrijd
triggers:
  - trigger: calendar
    entity_id: calendar.real_madrid
    event: start
    id: kickoff
  - trigger: calendar
    entity_id: calendar.real_madrid
    event: end
    id: final
actions:
  - choose:
      - conditions: [{ condition: trigger, id: kickoff }]
        sequence:
          - action: switch.turn_on
            target: { entity_id: switch.real_madrid_lampje }
      - conditions: [{ condition: trigger, id: final }]
        sequence:
          - action: switch.turn_off
            target: { entity_id: switch.real_madrid_lampje }
```

## Notes

- Create the target calendar first (*Settings → Devices & services → Add integration → Local Calendar*).
- Idempotent: re-running sync does not duplicate events that already exist (matched by summary + start).
- Only creates events for future matches; past ones are ignored.
