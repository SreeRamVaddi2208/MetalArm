# MetalArm design system

The web app is built on one calm system: near-black neutrals, one accent, a few type sizes, and about twenty primitives. Every screen is assembled from these pieces. To see them all in every state, open **`/design-system`** in a running app. It is not in any navigation.

- **Tokens:** `metalarm/theme.py`. This file is the spec's `tokens.py`; it keeps its old name because every module imports it.
- **Primitives:** `metalarm/ui/`.
- **Enforcement:** `tests/test_tokens.py` and `tests/test_contrast.py`.

## The ten rules

1. **One job per screen, one primary button.** Everything else is secondary, ghost or danger.
2. **One accent, used sparingly.** Forge orange covers about 10% of a screen at most. It goes on the primary button, the active tab, progress fills, the PR pill and selected chips.
3. **No second colour.** Danger red is for destructive actions only. Rank-tier colours live only inside `RankBadge` and the rank-up overlay; the lint checks this.
4. **Flat.** No shadows, gradients or glow, except in reward moments (rank-up, duel win).
5. **Three content sizes per screen.** One title size, body and caption. The display size is for a screen's single hero number. Button labels belong to the control.
6. **Progressive disclosure.** Advanced options go in a sheet. Rows lead to detail screens rather than expanding in place.
7. **One-handed.** Targets are at least 48 px (44 for icon buttons). The primary action is pinned low, above the tab bar.
8. **Every state designed.** Each list has a skeleton while loading, an empty state with one sentence and at most one action, and an error line.
9. **Calm words.** Sentence case and no shouting capitals. Numbers are exactly what the API returned; the client never computes points, PRs, ranks or streaks.
10. **It fits.** No horizontal scroll at 360 px. The column is 430 px at most, centred, with 20 px gutters.

## Tokens (`theme.py`)

Each token is also a CSS custom property (`--ma-bg`, `--ma-accent` and so on), written by `css_variables()` into the global stylesheet.

| Colour | Value | Used for |
|---|---|---|
| `BG` | `#0E0E10` | App background |
| `SURFACE` | `#17171A` | Cards, sheets, tab bar |
| `SURFACE_2` | `#202024` | Inputs, chips, pressed rows, avatars |
| `BORDER` | `#2A2A2F` | Hairlines and outlines only |
| `TEXT` | `#F4F4F2` | Primary text and hero numbers |
| `TEXT_2` | `#A1A1A8` | Secondary text, captions, icons |
| `TEXT_3` | `#6E6E76` | Placeholders, "last time" ghosts, disabled |
| `ACCENT` | `#FF6B2C` | See rule 2 |
| `ACCENT_SOFT` | accent at 14% | Selected chip or card, your row, PR row |
| `ON_ACCENT` | `#0E0E10` | Text on the accent |
| `DANGER` | `#E5484D` | Delete, discard, sign out |
| `TIER_COLORS` | E-S | `ui/rank_badge.py` and `components/level_up.py` only |

| Type | Font | Size / line | Weight |
|---|---|---|---|
| `DISPLAY` | Space Grotesk | 48 / 52 | 600 |
| `TITLE_LG` | Space Grotesk | 28 / 34 | 600 |
| `TITLE` | Space Grotesk | 20 / 26 | 600 |
| `BODY` | Manrope | 16 / 24 | 500 |
| `LABEL` | Manrope | 14 / 20 | 600 |
| `CAPTION` | Manrope | 12 / 16 | 500 |

Every style uses tabular numerals.

**Space** is `space(px)` on the scale 4, 8, 12, 16, 24, 32, 48. Any other value raises an error. The other layout tokens:
- `GUTTER` is 20 px, `CARD_PADDING` 16 px, `SECTION_GAP` 32 px;
- `TOUCH` is 48 px, `ICON_HIT` 44 px, `ROW_MIN` 56 px, `BUTTON_HEIGHT` 52 px;
- `MAX_WIDTH` is 430 px;
- `FLOAT_BOTTOM` is where toasts and banners float, clear of the tab bar and the pinned button.

**Shape:** `RADIUS` is 12 px (cards and inputs), `RADIUS_SHEET` 16 px, `RADIUS_PILL` for buttons and chips. **Motion:** `FAST` is 150 ms (taps), `BASE` 250 ms (sheets), with an ease-out curve. Both are switched off by the system's reduced-motion setting or the app's own (Profile > App).

## Primitives (`ui/`)

| Primitive | Where | Notes |
|---|---|---|
| `button(label, on_click, variant=primary\|secondary\|ghost\|danger, icon, disabled, full)` | primitives | 52 px pill. `link_button` is the same as a link |
| `icon_button(icon, label, on_click, href, badge)` | primitives | 44 px; `label` becomes the aria-label; `badge` adds an accent dot |
| `card(*children, on_click, href)` | primitives | Surface, 12 px radius, 16 px padding |
| `rows(*rows)` and `list_row(title, subtitle, leading, trailing, chevron, on_click, href)` | primitives | 56 px rows with hairlines between |
| `stat_tile(value, label, unit, big)` and `stat_group(*tiles)` | primitives | Groups of 2-3 |
| `section(title, *children, action, href, on_action)` | primitives | A titled group: spaced, not boxed |
| `chip`, `chips` | primitives | `chips` scrolls sideways |
| `segmented(options, selected, on_select)` | primitives | 2-4 options; each has `aria-pressed` |
| `progress_bar(scale, label)` | primitives | 4 px, accent fill |
| `pill(label, accent)` | primitives | The "PR" pill |
| `field(value, on_change, placeholder, type_, mode, on_blur, debounce)` | primitives | 52 px input on surface-2 |
| `stepper(value, on_change, on_minus, on_plus, unit, label)` | primitives | 48 px − and +, display-size number you can type into |
| `sheet(open_, on_close, *children, title, action)` | primitives | Bottom sheet with grab handle, 60% scrim and `role=dialog` |
| `empty_state(icon, line, action)`, `error_state(message, retry)`, `skeleton`, `skeleton_rows` | primitives | Rule 8 |
| `text(value, style, color)`, `number(value, unit, style)` | primitives | All text goes through these |
| `top_bar(title, back, trailing, large)`, `tab_bar`, `shell`, `avatar` | chrome | `large=True` for tab roots; `back` is a path or `"history"` |
| `rank_badge(rank, size=24\|48\|96)` | rank_badge | The only tier colour outside the overlay |
| `done_row` and `entry_panel` | set_row | Logged sets, and the focused card's steppers plus Log set |
| `path_card(path, selected, on_click)` | path_card | Onboarding and Settings |
| `line_chart(data)` | chart | One accent line, dots only where `mark` is set (the latest point, records) |
| `week_strip`, `month_calendar`, `body_map` | calendar, body_map | |
| `toast()` and `ToastState.show(message, icon)` | toast | Surface-2, near the bottom, 3 s |
| `program_card`, `program_shelf` | library | Name, one line, weeks · days · level; a "For your path" pill when the server says so |
| `workout_card` | library | A ListRow: duration · exercises · equipment |
| `path_chip(label, selected, own, href)` | library | A training path; the user's own marked with a dot |
| `schedule_grid(weeks)` | library | Weeks by days; rest days muted; scrolls sideways in its own box |

## Information architecture

| Tab | Root | Under it |
|---|---|---|
| Home | `/home` | `/leaderboard`, `/notifications`, `/u/<id>` |
| Train | `/train` (the live workout or its summary when there is one) | `/train/routine/<id>` (and `/new`), `/train/program/<id>` (your own programs) |
| Library | `/library` | `/library/path/<category>`, `/library/program/<slug>`, `/library/workout/<slug>`, `/library/exercises`, `/exercise/<id>` |
| Progress | `/progress` | `/progress/history`, `/progress/measurements`, `/progress/recovery`, `/session/<id>`, `/summary/<yyyy-mm>` |
| Profile | `/profile` | `/profile/people`, `/quests`, `/duels`, `/parties`, `/rewards`, `/about/credits` |

Signed out, there are `/login` and `/signup`; a new account then goes to `/welcome`. Old URLs redirect:
- `/workout` and `/routines` go to `/train`;
- `/explore` and `/train/exercises` go to `/library/exercises`; `/explore?tab=people` goes to `/profile/people`;
- `/train/program/<curated slug>` goes to `/library`;
- `/you` goes to `/progress`;
- `/dashboard` goes to `/home`;
- `/gallery` goes to `/design-system`.

`components/layout.py` `ROUTE_TABS` decides which tab lights up for each route.

## Adding a screen

1. Write the page in `pages/` as `shell(top_bar(...), ..., pinned=<the one primary, if any>)`. Use only `ui/` primitives and `theme` tokens; if you need a value the tokens lack, add a token.
2. Give every list its three states: a skeleton while loading, an empty state, and an error banner.
3. Put options behind a `sheet` rather than on the screen.
4. Register the route in `metalarm.py` with an `enter_*` guard, and map it to a tab in `ROUTE_TABS`.
5. Add it to `scripts/e2e/screens.mjs` if the default list doesn't cover it.
6. Check it:
   - `pytest frontend/tests` covers tokens and contrast;
   - `node scripts/e2e/screens.mjs <out> <email> <pw> --widths 360,390,430` checks for horizontal overflow;
   - look at the captures against the ten rules.
