# Calendar Clean Story Rules Patch

Version: `0.3.131-calendar-clean-story-rules-v1`

## Purpose

Clean calendar patch for 1206 runtime.

This patch removes route-like calendar phrasing and makes the calendar a world-pressure system:

- player controls Akira;
- calendar controls world state, NPC goals, timing windows and consequences;
- only the current day file is loaded during normal play;
- future dates are for timeskip/audit only;
- NPCs and pursuers require plausible time/distance before entering;
- sleep/rest/timeskip moves to the next meaningful beat;
- East Sector remains a living base, not a sterile prison/protocol scene.

## Files included

```text
app/production_runtime_patch.py
app/calendar_context_runtime_patch.py
app/calendar_scene_runtime_patch.py
calendar/calendar_index.yaml
calendar/story_spine_1206.yaml
calendar/east_sector_1206_calendar.yaml
calendar/days/_day_template.yaml
calendar/days/1206-08-31.yaml
calendar/days/1206-09-01.yaml
calendar/days/1206-09-05.yaml
calendar/days/1206-09-15.yaml
engine/calendar_day_runtime_rules.md
state/calendar_runtime.json
```

## Important behavior

The calendar must not write Akira's actions.
It must not reference material outside project files/current state.
It must not make conditional arrivals instant.
It must not make NPCs know hidden contents, motives, routes or facts without scene access.
