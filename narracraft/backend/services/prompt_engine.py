"""Veo 3 R2V prompt generation engine.

Generates ready-to-paste prompts from script data + character descriptions + franchise elements.
No LLM calls needed — purely template-based assembly.
"""


def generate_veo3_prompts(
    scene: dict,
    visual_aesthetic: str,
    iconic_elements: str,
) -> str:
    """Generate a single Veo 3 R2V prompt for a scene.

    Args:
        scene: Dict with keys: dialogue, expression, environment, camera_angle,
               character_name, appearance, outfit, voice_direction
        visual_aesthetic: Franchise visual style keywords
        iconic_elements: Franchise iconic elements to include
    """
    character_name = scene.get("character_name", "A person")
    appearance = scene.get("appearance", "")
    outfit = scene.get("outfit", "")
    dialogue = scene.get("dialogue", "")
    expression = scene.get("expression", "")
    environment = scene.get("environment", "")
    camera_angle = scene.get("camera_angle", "Close-up")
    voice_direction = scene.get("voice_direction", "")

    # Build character description
    char_desc = ""
    if appearance:
        char_desc = appearance
    if outfit:
        char_desc += f", {outfit}" if char_desc else outfit

    if not char_desc:
        char_desc = "a person"

    # Build voice/emotion direction
    voice_part = ""
    if voice_direction:
        voice_part = f"in {voice_direction}"
    elif expression:
        voice_part = f"in a {expression} voice"
    else:
        voice_part = "in a natural voice"

    # Build dialogue part
    dialogue_part = ""
    if dialogue:
        # Determine pronoun from appearance
        pronoun = "They"
        appearance_lower = (appearance or "").lower()
        if any(w in appearance_lower for w in ["woman", "female", "girl", "she", "her "]):
            pronoun = "She"
        elif any(w in appearance_lower for w in ["man", "male", "boy", "he ", "his "]):
            pronoun = "He"

        dialogue_part = f'{pronoun} says {voice_part}, "{dialogue}"'

    # Build environment with franchise elements
    env_part = environment or ""
    if iconic_elements and iconic_elements.lower() not in env_part.lower():
        # Remind about franchise elements if not already in environment description
        env_part += f" Franchise elements visible: {iconic_elements}."

    # Assemble the full prompt
    parts = [
        f"{camera_angle} of {char_desc}.",
        env_part + "." if env_part and not env_part.endswith(".") else env_part,
        dialogue_part + "." if dialogue_part and not dialogue_part.endswith(".") else dialogue_part,
        "No background music. Photorealistic, 9:16 vertical, cinematic lighting.",
    ]

    return " ".join(p for p in parts if p).strip()


def generate_character_prompt(
    character: dict,
    franchise: dict,
) -> str:
    """Generate a Google Flow character reference image prompt.

    Args:
        character: Dict with keys: name, appearance, outfit, personality
        franchise: Dict with keys: name, visual_aesthetic, iconic_elements
    """
    appearance = character.get("appearance", "")
    outfit = character.get("outfit", "")
    personality = character.get("personality", "")
    iconic_elements = franchise.get("iconic_elements", "")
    visual_aesthetic = franchise.get("visual_aesthetic", "")

    # Determine expression from personality
    expression_hint = "confident and alert"
    if personality:
        traits = personality.lower()
        if "haunted" in traits or "weary" in traits:
            expression_hint = "haunted, world-weary but defiant"
        elif "fierce" in traits or "angry" in traits:
            expression_hint = "fierce, jaw tight, eyes intense"
        elif "scared" in traits or "uncertain" in traits:
            expression_hint = "uncertain but alert, slightly wide eyes"

    prompt = f"""Photograph, shot on Canon EOS R5, 85mm portrait lens, f/1.8 aperture, \
shallow depth of field. 9:16 vertical composition.

Close-up portrait of {appearance}. {outfit}.

Expression: {expression_hint}.

Background: environment with {iconic_elements} visible. {visual_aesthetic} atmosphere.

Beauty portrait lighting — soft key light from front-right, warm fill. Bright catch-lights \
in eyes. Natural skin with visible pores, real fabric textures. Real person cosplay photography, \
editorial portrait quality, DSLR, photographic realism."""

    return prompt
