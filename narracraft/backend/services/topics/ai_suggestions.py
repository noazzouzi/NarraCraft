"""AI-generated topic suggestions.

Generates additional topic ideas based on franchise context.
Uses the franchise registry's topic seeds as examples to generate more.
In production, this would call Gemini via Playwright.
For now, it generates suggestions from patterns in existing seeds.
"""

import random
from dataclasses import dataclass


@dataclass
class AISuggestion:
    title: str
    description: str
    category: str  # characters, dev_design, lore, easter_egg, cut_content, memes
    requires_fact_check: bool = True  # AI-generated topics must be verified


# Topic generation templates per category
TEMPLATES: dict[str, list[str]] = {
    "characters": [
        "The original design for {character} was completely different",
        "{character}'s backstory changed dramatically during development",
        "The real inspiration behind {character}'s design",
        "A hidden detail about {character} that most fans missed",
        "{character} was originally meant to have a different role",
    ],
    "dev_design": [
        "A scrapped mechanic that would have changed the entire game",
        "The developer's original vision was very different from the final product",
        "A hardware limitation that accidentally created an iconic feature",
        "The game was almost cancelled during development — here's why",
        "A specific real-world location that inspired the game's setting",
    ],
    "lore": [
        "A hidden connection between two seemingly unrelated parts of the story",
        "The real mythology that inspired the story's central concept",
        "A detail in the opening that foreshadows the ending",
        "The philosophical debate hidden within the story",
        "A character's name reveals their fate in the original language",
    ],
    "easter_egg": [
        "A reference to another franchise hidden in plain sight",
        "A developer message hidden in the game files",
        "A secret room/area that most players never find",
        "A hidden interaction between characters that triggers under specific conditions",
        "A number/date that appears repeatedly and has a hidden meaning",
    ],
    "cut_content": [
        "An entire storyline that was cut from the final version",
        "A character that was designed but never made it into the game",
        "A gameplay mechanic that was too ambitious for the hardware",
        "Deleted scenes that reveal a different version of the story",
        "A scrapped ending that would have changed everything",
    ],
    "memes": [
        "How a bug became the franchise's most beloved feature",
        "The unintentionally hilarious moment that became a community legend",
        "A piece of dialogue that was never meant to be taken seriously",
        "The most famous misquote from the franchise",
        "A design choice that fans turned into an iconic meme",
    ],
}


def generate_suggestions(
    franchise_name: str,
    character_names: list[str] | None = None,
    existing_seeds: list[str] | None = None,
    count: int = 10,
) -> list[AISuggestion]:
    """Generate topic suggestions based on franchise context.

    In production, this would call an LLM. For now, uses templates.
    """
    suggestions: list[AISuggestion] = []
    chars = character_names or ["the main character"]

    all_templates: list[tuple[str, str]] = []
    for category, templates in TEMPLATES.items():
        for template in templates:
            all_templates.append((category, template))

    random.shuffle(all_templates)

    for category, template in all_templates[:count]:
        title = template
        if "{character}" in title:
            title = title.replace("{character}", random.choice(chars))

        # Skip if too similar to existing seeds
        if existing_seeds:
            if any(_similarity(title, seed) > 0.6 for seed in existing_seeds):
                continue

        suggestions.append(AISuggestion(
            title=f"{franchise_name}: {title}",
            description=f"AI-generated topic suggestion for {franchise_name}. Requires fact-checking before use.",
            category=category,
            requires_fact_check=True,
        ))

    return suggestions[:count]


def _similarity(a: str, b: str) -> float:
    """Simple word overlap similarity."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)
