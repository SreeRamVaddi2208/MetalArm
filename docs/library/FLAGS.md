# Library tab: flags

This records where the build met something in the spec ("MetalArm — Library & Category Programs", 7 Oct 2026) that didn't match the code, how each one was settled, and what needs a human before launch.

## Read before launch

**The seeded programming needs a human review.** The build wrote 9 programs, 12 standalone workouts and 33 program-day workouts. They are in `backend/app/data/library_catalog.json`, one exercise per line, so they're easy to read and edit.

All of them pass the content validator (`backend/app/core/catalog_validator.py`):
- every exercise exists;
- every schedule adds up;
- every session fits its training path's rep and rest bands.

The validator can't judge whether a program is *good training*. Sree Ram, or a coach he trusts, should read it before launch. Program detail shows "These are templates, not coaching. Adjust the load to your ability." Things worth a second look:

- **Intermediate Strength Waves** and **Meet Prep Peak** express their waves through a note on the main lift ("5s, then 3s, then singles") and a 1–5 or 1–3 rep range. They don't vary the template week by week. The schedule format supports per-week overrides if real week-by-week waves are wanted later.
- **Athletic holds and carries** (plank, side plank, farmer's carry, bear crawl) count seconds or steps as "reps", with a note on each row. The workout screen logs them as reps.
- **Athletic rests aim for the spec's 30–45 s.** Some plyometric work uses 60 s, which is inside the band below.

## Spec versus code

| # | The spec said | The code had | What was done |
|---|---|---|---|
| 1 | Phase 1: build multi-exercise sessions | Already there: multiple exercise cards, the picker sheet, sessions pre-loaded from routines and presets, rehydration | Checked, not rebuilt. A Library start reuses that path: the workout becomes a routine of the user's own, keyed on `routines.preset_slug`, as the ready-made workouts already were. |
| 2 | Tables `Program`, `WorkoutTemplate`, … | `programs` is the user's own programs | New tables with non-clashing names: `library_workouts`, `library_workout_exercises`, `library_programs`, `library_program_days`, `program_enrollments`. |
| 3 | A new catalog | 6 curated programs and 3 ready-made workouts in JSON, behind `/programs/curated` and `/workouts/presets`, which iOS may read | Folded into the one catalog file as `legacy_source` entries, unpublished in the Library. The old endpoints rebuild their exact old data from it; `tests/test_catalog_compat.py` pins this against the original files, kept in `backend/tests/fixtures/`. |
| 4 | Path value "athletic" | `athlete` (`users.character_class`) | The code value is kept. "Athletic" is its label. |
| 5 | Athletic rest 30–45 s | The profile says 60 s | The validator's bands contain both: athlete 30–60 s, bodybuilder 60–120 s, powerlifter primary lifts 180–300 s and accessories 60–150 s. Mobility work is exempt from rep bands, with rest capped at 60 s. |
| 6 | Powerlifter "1–6 on primary lifts" | No notion of a primary lift | Primary means an exercise tagged `big3` or `compound_heavy`, unless the slot says `"role": "accessory"`. A powerlifting session has at most 2 primaries and 4 accessories, and accessories take 3–15 reps. |
| 7 | Emphasis tag `circuit` | `ExerciseTag` has no `circuit`, and tags describe exercises, not sessions | No new tag. A circuit is slots sharing a `superset` number, plus `circuit` in the workout's `focus_tags`. |
| 8 | `API_CONTRACT.md` | The contract is `docs/api-contract.md`, generated from OpenAPI | The route docstrings were written, and the file was regenerated with `scripts/generate_api_contract.py`. |
| 9 | Tab order Home, Train, Library, Progress, Profile | 4 tabs (the redesign) | Five tabs in that order. Programs, ready-made workouts and the exercise browser moved from Train to Library. Train keeps Up next, your routines, your own programs and Start empty workout. |
| 10 | Missing exercises | No box jump, jump squat, farmer's carry and others | Ten added, with MetalArm diagrams: box-jump, jump-squat, farmers-carry, mountain-climber, skater-jump, medicine-ball-slam, lateral-lunge, bear-crawl, inchworm and dead-bug. |
| 11 | A user follows a program | No enrollment existed | `program_enrollments`, one active per user. Following another program pauses the first. Finishing a session started from the program's next workout moves it on, skipping rest days. That bookkeeping runs after every reward is settled and changes no points; a test proves an enrolled finish pays exactly what a non-enrolled one does. |

## Design calls made

- **Equipment filter:** shows what you can do *with* the equipment you pick (the item's equipment is a subset of yours). It doesn't mean "uses this equipment".
- **Search:** the Library's search icon opens the filter sheet on your path's view (`/library/path/<path>?filters=1`). There is no free-text search across programs; the exercise browser keeps its own search.
- **Routines:** a started or saved Library workout appears in the user's routines, as ready-made workouts always did. Program days a user has started appear there too.
- **Catalog changes:** re-importing the catalog replaces a workout's exercises and a program's days. Enrollments keep their week and day numbers, so they survive. A slug removed from the file is unpublished, never deleted.
- **Content limits:** cardio-category exercises (jump rope, high knees) are left out of Library content, because the workout screen logs them as duration and distance rather than reps.

## The spec's open questions: defaults taken

| Question | Default |
|---|---|
| Tab order | Library third, as written. |
| Exercises in the Library | Yes. The exercise browser moved to `/library/exercises`, linked from Library home. |
| Content authorship | Drafted by the build; needs review (see above). |
| Hybrid users | A user can follow any path's program, with no warning. The "For your path" pill shows what matches. |
| Load progression | Not in this pass. Enrollment tracks week and day only. |
| Cover art | Text-only cards in v1. |

## Independent review

A reviewer sub-agent read the new screens at 360, 390 and 430 px against the design rules. Rule 1 (one primary per screen), the accent limit and "no glow" held everywhere.

**Fixed:**
- Rows that are links now draw their hairline (`.ma-rows > a`). This also affected Train's lists before.
- The path chips, program shelf and schedule grid bleed to the screen edge, so they read as scrolling rather than clipped.
- Program titles take two lines.
- The path view drops the "For your path" pill, since every card there would carry it.
- The equipment label reads "EZ bar".
- The home workout list has a heading.

**Not a bug:** "Save to routines hidden under the pinned button" came from the full-page capture. On a real 360 px screen, scrolling to the end puts it at y 588–640, clear of the pinned button at 672.

**Kept:**
- The type scale follows the redesign's reading (`docs/redesign/FLAGS.md` #8).
- Exercise names stay as the library writes them.
- The thumbnail styles are the exercise library's and are out of scope here.
