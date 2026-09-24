"""What a rank-up looks like, per tier, as data.

The ladder MetalArm actually uses is E-D-C-B-A-S, shown as Untrained, Novice,
Intermediate, Advanced, Elite and World Class (see ranks.py). Untrained is
where everyone starts, so there are five promotions to celebrate, and each one
is louder than the last: Novice is a flourish, World Class is an event.

Every tier plays the SAME sequence - flash, shake, zoom, badge, ladder line,
settle - and differs only in the numbers below. Adding a sixth tier is a row
here, not a new animation. Nothing in this module imports Reflex, so the
budgets can be tested without building the frontend.

The palette stays inside MetalArm's steel-to-white identity (theme.RANK_COLORS)
rather than a bronze-to-jewel ladder: warm gold and a single jewel tone are
held back for Elite and World Class, which is what makes them read as rarer.
"""

from dataclasses import dataclass, field

# The whole overlay is DOM elements animated with transform and opacity, so the
# element count IS the performance budget. 72 keeps the heaviest tier inside a
# frame on a mid-range phone; the test suite holds every tier to it.
MAX_PARTICLES = 72
# A reward moment must never feel like it is holding the app hostage.
MAX_DURATION_MS = 4500


@dataclass(frozen=True)
class Tier:
    """One promotion: the rank being entered."""

    rank: str
    # --- Colour -----------------------------------------------------------
    base: str           # the badge itself
    glow: str           # the halo behind it, and the rings
    jewel: str          # accents: gems, filigree, the crown's stones
    # --- Iconography ------------------------------------------------------
    # plain -> laurel -> laurel+gems -> crown -> crown+filigree
    ornament: str
    # --- Particles --------------------------------------------------------
    # Layer names are CSS classes: spark (fast metal shards), glow (soft trail),
    # ember (slow floating dust), ambient (lingers after the burst settles).
    layers: tuple[str, ...]
    sparks: int         # per layer
    rings: int
    # --- Motion -----------------------------------------------------------
    shake_px: float     # 0 = no camera shake
    zoom: float         # 1.0 = no zoom
    shock: bool         # the wide shockwave ring that outruns the others
    pop: float          # how hard the level counter lands; 1.0 = no bounce
    duration_ms: int
    # --- Sound and touch --------------------------------------------------
    sound: tuple[str, ...]      # chime, shimmer, bass, fanfare
    haptic: tuple[int, ...]     # navigator.vibrate pattern, ms
    # --- Copy -------------------------------------------------------------
    line: str = ""

    @property
    def particles(self) -> int:
        return self.sparks * len(self.layers)


STEEL = "#9a9aa2"
BRIGHT = "#c0c0c8"
PALE = "#e0e0e6"
WHITE = "#ffffff"
GOLD = "#d9b06a"
SAPPHIRE = "#6f8fd6"
RUBY = "#c05a6a"

# Ascending. Keyed by the rank ENTERED - Untrained ("E") is the starting tier
# and has no promotion into it.
TIERS: dict[str, Tier] = {
    "D": Tier(
        rank="D",
        base=STEEL, glow=STEEL, jewel=STEEL,
        ornament="plain",
        layers=("spark",), sparks=16, rings=1,
        shake_px=0, zoom=1.0, shock=False, pop=1.0, duration_ms=1700,
        sound=("chime",), haptic=(18,),
        line="First rung. The bar goes up from here.",
    ),
    "C": Tier(
        rank="C",
        base=BRIGHT, glow=BRIGHT, jewel=STEEL,
        ornament="laurel",
        layers=("spark", "glow"), sparks=18, rings=2,
        shake_px=0, zoom=1.04, shock=False, pop=1.04, duration_ms=2300,
        sound=("chime", "shimmer"), haptic=(18, 60, 28),
        line="No longer new to this.",
    ),
    "B": Tier(
        rank="B",
        base=PALE, glow=PALE, jewel=GOLD,
        ornament="gems",
        layers=("spark", "glow", "ember"), sparks=20, rings=3,
        shake_px=3, zoom=1.07, shock=False, pop=1.08, duration_ms=2900,
        sound=("chime", "shimmer", "bass"), haptic=(28, 50, 28),
        line="Advanced. Most people never get here.",
    ),
    "A": Tier(
        rank="A",
        base=WHITE, glow=GOLD, jewel=SAPPHIRE,
        ornament="crown",
        layers=("spark", "glow", "ember"), sparks=22, rings=3,
        shake_px=5, zoom=1.1, shock=True, pop=1.12, duration_ms=3600,
        sound=("chime", "shimmer", "bass"), haptic=(34, 40, 34, 40, 50),
        line="Elite. The numbers speak for themselves.",
    ),
    "S": Tier(
        rank="S",
        base=WHITE, glow=GOLD, jewel=RUBY,
        ornament="regalia",
        layers=("spark", "glow", "ember", "ambient"), sparks=18, rings=4,
        shake_px=7, zoom=1.14, shock=True, pop=1.18, duration_ms=4400,
        sound=("fanfare", "shimmer", "bass"), haptic=(50, 60, 34, 60, 34, 90, 70),
        line="World Class. Nothing above this.",
    ),
}

# The tier a level-up (not a rank-up) borrows: the shared sequence at its
# quietest, so the two beats cannot be confused.
LEVEL_UP = Tier(
    rank="",
    base=STEEL, glow=STEEL, jewel=STEEL,
    ornament="plain",
    layers=("spark",), sparks=16, rings=1,
    shake_px=0, zoom=1.0, shock=False, pop=1.0, duration_ms=1500,
    sound=("chime",), haptic=(14,),
    line="Keep going.",
)


def tier_for(rank: str) -> Tier:
    """The config for the rank just entered. An unknown or missing rank falls
    back to the quietest tier rather than rendering nothing: a celebration that
    silently does not happen is worse than a plain one."""
    return TIERS.get(rank, LEVEL_UP)


def particles(tier: Tier) -> list[dict[str, str]]:
    """One entry per particle: its CSS class, angle, travel and delay.

    Deterministic - the same tier always throws the same burst, so a screenshot
    diff or a recorded tour is reproducible. Angles are spread evenly and each
    layer is offset, so the layers interleave instead of stacking into spokes.
    """
    out: list[dict[str, str]] = []
    for depth, layer in enumerate(tier.layers):
        for i in range(tier.sparks):
            out.append(
                {
                    "cls": f"lf-p lf-{layer}",
                    "a": f"{(360 / tier.sparks) * i + depth * 11:.1f}deg",
                    "d": f"{96 + (i * 37) % 52 + depth * 18}px",
                    # Ambient dust does not radiate; it drifts up from a spread
                    # of starting points, so it needs a horizontal offset.
                    "x": f"{(i * 97) % 100}%",
                    "delay": f"{(i % 5) * 24 + depth * 40}ms",
                }
            )
    return out


def previous(rank: str) -> str:
    """The tier below this one, for the "Intermediate -> Advanced" line when a
    celebration is being previewed rather than earned."""
    ladder = ["E", *TIERS]
    index = ladder.index(rank) if rank in ladder else 0
    return ladder[max(0, index - 1)]
