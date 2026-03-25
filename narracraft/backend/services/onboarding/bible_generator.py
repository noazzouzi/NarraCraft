"""Character bible generator for franchise onboarding.

Takes wiki text, infobox data, and user-selected reference images
to produce a structured character bible for consistent AI generation.
"""

import re
from dataclasses import dataclass, field


@dataclass
class CharacterBible:
    archetype_id: str
    visual_description: str
    character_bible: str
    is_narrator: bool = False
    source_character_name: str = ""  # Real name — never used in AI prompts
    source_references: list[str] = field(default_factory=list)


def generate_archetype_id(character_name: str) -> str:
    """Generate an abstract archetype ID from a character name.

    This ID is used in prompts and file paths — never the real name.
    """
    # Simple heuristic mapping — in production, LLM would generate these
    name_lower = character_name.lower().strip()

    # Common archetype patterns
    archetype_keywords = {
        "hero": ["hero", "protagonist", "main"],
        "villain": ["villain", "antagonist", "evil", "dark"],
        "mentor": ["mentor", "teacher", "master", "sage"],
        "rival": ["rival", "opponent"],
        "warrior": ["warrior", "fighter", "soldier", "knight"],
        "mage": ["mage", "wizard", "sorcerer", "witch"],
        "rogue": ["rogue", "thief", "spy", "ninja"],
        "healer": ["healer", "medic", "doctor"],
    }

    # Default: generate from name structure
    words = re.sub(r"[^a-z\s]", "", name_lower).split()
    if not words:
        return "unknown_character"

    return "_".join(words[:2])


def generate_bible_from_wiki(
    character_name: str,
    wiki_summary: str,
    infobox: dict[str, str],
    wiki_html: str = "",
) -> CharacterBible:
    """Generate a character bible from wiki data.

    The bible describes the character's appearance without using their name,
    making it safe to use in AI image generation prompts.
    """
    # Extract physical attributes from infobox
    physical_attrs = []
    attr_keys = {
        "gender": ["gender", "sex"],
        "age": ["age"],
        "height": ["height"],
        "weight": ["weight"],
        "hair": ["hair", "hair_color", "hair color"],
        "eyes": ["eye", "eyes", "eye_color", "eye color"],
        "blood_type": ["blood_type", "blood type"],
    }

    extracted = {}
    for attr_name, keys in attr_keys.items():
        for key in keys:
            for ib_key, ib_val in infobox.items():
                if key in ib_key.lower() and ib_val:
                    extracted[attr_name] = ib_val
                    break
            if attr_name in extracted:
                break

    # Build visual description
    parts = []
    gender = extracted.get("gender", "")
    if gender:
        parts.append(gender.capitalize())

    age = extracted.get("age", "")
    if age:
        parts.append(f"age {age}")

    hair = extracted.get("hair", "")
    if hair:
        parts.append(f"{hair.lower()} hair")

    eyes = extracted.get("eyes", "")
    if eyes:
        parts.append(f"{eyes.lower()} eyes")

    # Extract appearance info from summary
    appearance_sentences = _extract_appearance_from_text(wiki_summary)

    visual_desc = ", ".join(parts) if parts else "character with distinctive appearance"

    # Build full character bible
    bible_parts = []
    if parts:
        bible_parts.append(". ".join(filter(None, [
            gender.capitalize() if gender else None,
            f"appears to be {age}" if age else None,
        ])))

    if appearance_sentences:
        bible_parts.extend(appearance_sentences[:3])

    # Add outfit/gear from infobox if available
    for key in ["occupation", "weapon", "abilities", "outfit"]:
        for ib_key, ib_val in infobox.items():
            if key in ib_key.lower() and ib_val:
                bible_parts.append(f"{key.capitalize()}: {ib_val}")
                break

    bible_text = " ".join(bible_parts) if bible_parts else (
        f"A distinctive character from the series. {wiki_summary[:300]}"
    )

    archetype_id = generate_archetype_id(character_name)

    return CharacterBible(
        archetype_id=archetype_id,
        visual_description=visual_desc,
        character_bible=bible_text[:600],
        source_character_name=character_name,
    )


def _extract_appearance_from_text(text: str) -> list[str]:
    """Extract appearance-related sentences from wiki text."""
    appearance_keywords = [
        "wears", "wearing", "dressed", "outfit", "armor", "uniform",
        "tall", "short", "muscular", "slender", "slim", "athletic",
        "hair", "eyes", "scar", "tattoo", "mark",
        "appears", "appearance", "looks", "build", "physique",
    ]

    sentences = re.split(r"[.!?]+", text)
    appearance_sentences = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 20:
            continue
        lower = sentence.lower()
        if any(kw in lower for kw in appearance_keywords):
            # Clean up the sentence
            clean = re.sub(r"\[.*?\]", "", sentence).strip()
            if clean:
                appearance_sentences.append(clean)

    return appearance_sentences[:5]
