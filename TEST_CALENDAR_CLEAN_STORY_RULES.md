# Test: Calendar Clean Story Rules

## 1. Current day only

Call fast/context or scene-packet on date `1206-08-31`.
Expected:

- loads `calendar/days/1206-08-31.yaml`;
- does not load `1206-09-01.yaml`, `1206-09-05.yaml`, `1206-09-15.yaml` during normal scene.

## 2. Player control

Input: player gives a specific action for Akira.
Expected:

- scene responds to that action;
- scene does not replace it with calendar route;
- Akira does not speak or decide without player input.

## 3. Hesitation

Input: player waits/does nothing repeatedly.
Expected:

- NPCs continue according to goals;
- scene pressure increases;
- no empty stalling loop.

## 4. Conditional arrival timing

Trigger a faint sign for Raiden or pursuers.
Expected:

- they do not appear instantly unless current_state already placed them nearby;
- scene accounts for path/time/distance.

## 5. Sleep/rest

Input: player writes that Akira sleeps/rests until morning.
Expected:

- next scene starts at a meaningful beat;
- no menu asking why/how she wakes up.

## 6. NPC visibility

Hide information inside inventory/state but do not reveal it in scene.
Expected:

- NPCs can suspect or ask;
- NPCs cannot know hidden contents/motive/route as fact.
