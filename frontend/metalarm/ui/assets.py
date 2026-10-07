"""The asset registry: one lookup from a key ("muscle/chest", "equipment/
barbell", "placeholder/exercise") to the artwork shown for it.

Everything drawn in the app goes through here, so commissioned artwork
replaces a placeholder by changing one entry, never a component. Licensed
library artwork (wger, CC-BY-SA) arrives per exercise from the API with its
credit; this registry holds MetalArm's own drawings and placeholders.
"""

# Lucide icons standing in for equipment artwork until it is drawn.
EQUIPMENT_ICONS: dict[str, str] = {
    "barbell": "dumbbell",
    "dumbbell": "dumbbell",
    "bodyweight": "person-standing",
    "cable": "cable",
    "machine": "cog",
    "smith_machine": "columns-3",
    "kettlebell": "weight",
    "band": "infinity",
    "ez_bar": "dumbbell",
    "trap_bar": "hexagon",
    "plate": "circle-dot",
    "cardio_machine": "activity",
    "other": "shapes",
}



def equipment_icon(code: str) -> str:
    return EQUIPMENT_ICONS.get(code, "shapes")
