# First feature: book a performance, refuse a clash, keep the lineup

Product: Festival Architect (brief in `docs/product-brief.md`). User: the festival organiser.

## Planning sheet

1. **Product and user:** Festival Architect, used by the organiser of Carcavelos Sound.
2. **Trigger:** The organiser picks an artist, a stage and a start time, then clicks *Book*.
3. **Before:** The artist catalogue and the two stages exist. The lineup may already hold other bookings.
4. **Rule:** Refuse the booking when it overlaps another performance on the same stage, starts before 14:00, ends after 23:00, books an artist twice, or pushes the fees over €10,000.
5. **After:** One new row in the saved lineup (artist, stage, start). The timetable and the remaining budget change.
6. **Restart:** After stopping and reopening the app, the same bookings, timetable and totals are shown.

## Why

The organiser can build a lineup that is guaranteed to run: no clashes on a stage, inside festival hours, within budget. Work survives closing the app.

## What

- Show the catalogue with genre, fee and set duration; mark artists that are already booked (FA01).
- Book an artist on a stage at a start time; the end time is the start plus the artist's duration (FA02).
- Refuse a booking that breaks FA R1, FA R2 or FA R4 and say why. A refused booking changes nothing in the saved data.
- Two artists may play at the same time on different stages (FA R3).
- Show each stage's performances in time order with start and end, plus total fees and remaining budget (FA03).
- Save every accepted booking immediately, so it survives a restart.

## Out of scope

Moving or removing a booking (FA04), finalising and reopening the plan (FA05). Those are the next task. No accounts, payments or ticket sales.

## Done when

- **Accepted:** with an empty lineup, The Tidewaters (60 min) on Beach Stage (A) at 16:00 is booked, shown as 16:00–17:00, and the remaining budget drops from €10,000 to €6,500.
- **Rejected, data unchanged:** Os Gaivotas (45 min) on Beach Stage at 16:30 is refused with a reason that names the clash; the lineup still holds only The Tidewaters. At 17:00 the same booking is accepted (touching is allowed).
- **Boundaries:** a 60-minute set at 13:59 or 22:01 is refused, at 22:00 accepted.
- **Restart:** stop the app (Ctrl+C), start it again; both bookings and the €5,000 remaining budget are still there.
