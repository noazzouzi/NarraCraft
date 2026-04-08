"""LLM prompt templates for NarraCraft.

Each function returns a (system_prompt, user_prompt) tuple ready for the LLM provider.
"""

FRANCHISE_SYSTEM = """You are a gaming and anime franchise expert AND a character design expert \
specializing in extremely detailed visual descriptions for AI image generation. You know franchise \
lore, characters, visual aesthetics, and iconic elements across all major franchises. When \
describing characters, you describe them as REAL PEOPLE in cosplay being photographed on a \
professional set — practical costumes with real fabrics, natural human features, real skin texture. \
NEVER describe characters as CGI, game renders, or animated. You provide accurate, detailed \
information formatted as JSON."""

CHARACTER_SYSTEM = FRANCHISE_SYSTEM

SCRIPT_SYSTEM = """You are a script writer for short-form vertical video content (YouTube Shorts, \
TikTok, Instagram Reels). You write scripts where characters narrate directly to camera, sharing \
surprising lore facts. Each character speaks AS themselves — in first person, with their own \
personality and speech style. This is NOT a neutral narrator."""


def franchise_onboarding(name: str, category: str) -> tuple[str, str]:
    """Generate franchise details + all main characters with full Flow prompts in ONE call."""
    prompt = f"""For the {category} franchise "{name}", provide a COMPLETE onboarding package:

1. "visual_aesthetic": Comma-separated visual style keywords for AI image generation \
(e.g., "post-apocalyptic, overgrown urban, survival horror, muted earth tones")

2. "iconic_elements": Comma-separated list of visual elements fans would instantly recognize. \
Include: logos, signs, symbols, props, weapons, creatures, iconic locations, environmental details. \
Be very specific — these will appear in AI-generated scenes.

3. "characters": An array of the 4-5 most important/popular characters. For EACH character provide:
  - "name": Full character name
  - "role": One-line role description
  - "appearance": Extremely detailed physical description as a REAL PERSON — exact age range, \
exact hair color/style (length, texture, parting), exact eye color, face shape, skin tone/texture \
(scars, stubble, freckles, wrinkles, sun damage), build, ALL distinguishing features with exact \
locations (scars, tattoos with design and placement, facial hair, etc)
  - "outfit": Every clothing item with specific colors, materials, textures, condition. Include \
shirt/top, jacket/outer layer, pants, footwear, accessories (watches, jewelry, belts, holsters), \
visible weapons, bags/straps, badges. Describe as REAL worn costume pieces (worn leather, faded \
cotton, frayed denim).
  - "personality": 3-5 key traits (comma-separated)
  - "speech_style": How they talk — tone, accent, mannerisms. Include an example line.
  - "flow_prompt": A COMPLETE ready-to-paste Google Flow image generation prompt following this \
EXACT structure (fill in ALL values, no brackets or placeholders):

Photograph, shot on Canon EOS R5, 85mm portrait lens, f/1.8 aperture, shallow depth of field. \
9:16 vertical composition.

Close-up portrait of [FILL: full appearance description]. [FILL: full outfit description].

Standing in [FILL: franchise-specific environment with 2-3 iconic elements visible in background].

Expression: [FILL: strong specific emotion with micro-expression details].

Beauty portrait lighting — [FILL: specific lighting for franchise atmosphere]. Natural skin with \
visible pores, [FILL: skin-specific details]. Real person cosplay photography, editorial portrait \
quality, DSLR, photographic realism.

IMPORTANT: The flow_prompt must be a COMPLETE string with ALL actual character details filled in, \
ready to copy-paste directly into Google Flow. Do NOT leave any brackets or placeholders.

Return as a JSON object with keys: visual_aesthetic, iconic_elements, characters"""

    return FRANCHISE_SYSTEM, prompt


def character_onboarding(
    character_name: str,
    franchise_name: str,
    franchise_category: str,
    visual_aesthetic: str = "",
    iconic_elements: str = "",
) -> tuple[str, str]:
    """Generate extremely detailed character description + ready-to-use Flow prompt."""
    prompt = f"""For the character "{character_name}" from the {franchise_category} franchise "{franchise_name}", \
provide an extremely detailed character profile for AI image generation.

Franchise visual aesthetic: {visual_aesthetic}
Franchise iconic elements: {iconic_elements}

Return a JSON object with these keys:

1. "appearance": Extremely detailed physical description as a REAL PERSON — exact age range, \
exact hair color and style (length, texture, parting, any distinctive styling), exact eye color, \
face shape (angular, round, square, oval), skin tone and texture (scars, stubble, freckles, \
wrinkles, sun damage), build (lean, muscular, stocky, slim), height impression, and ALL \
distinguishing features (specific scars with location, tattoos with design and placement, \
facial hair style, piercings, etc). Describe as a real human, not a game model.

2. "outfit": Every single clothing item with specific colors, materials, and textures. \
Include: shirt/top (color, pattern, material, condition), jacket/outer layer (type, color, \
material, wear level), pants (color, type, material), footwear (type, color), accessories \
(watches, jewelry, belts, holsters), weapons visible, bags/straps, badges/patches. Describe \
as real costume pieces with real fabric textures (worn leather, faded cotton, frayed denim, etc).

3. "personality": 3-5 key character traits (comma-separated)

4. "speech_style": How this character talks — tone, vocabulary level, accent/dialect, \
emotional tendencies, verbal mannerisms. Include a typical example line they might say.

5. "flow_prompt": A COMPLETE, ready-to-paste Google Flow image generation prompt for this \
character. This prompt must follow this exact structure:

Photograph, shot on Canon EOS R5, 85mm portrait lens, f/1.8 aperture, shallow depth of field. \
9:16 vertical composition.

Close-up portrait of [FULL APPEARANCE DESCRIPTION WITH EVERY DETAIL FROM ABOVE]. \
[FULL OUTFIT DESCRIPTION WITH EVERY ITEM].

Standing in [FRANCHISE-SPECIFIC ENVIRONMENT using iconic elements: {iconic_elements}]. \
[2-3 specific iconic props or environmental details visible in the background].

Expression: [STRONG SPECIFIC EMOTION with micro-expression details — brow position, jaw, eyes].

Beauty portrait lighting — [specific lighting that fits the franchise atmosphere]. \
Natural skin with visible pores, [skin-specific details]. Real person cosplay photography, \
editorial portrait quality, DSLR, photographic realism.

The flow_prompt must be a single complete string, NOT a template with brackets — fill in ALL \
values with the actual character details. It should be ready to copy-paste directly into Google Flow."""

    return CHARACTER_SYSTEM, prompt


def topic_suggestions(
    franchise_name: str,
    category: str,
    characters: list[dict],
    iconic_elements: str,
) -> tuple[str, str]:
    """Generate topic suggestions for a franchise with character context."""
    # Build rich character context so topics are specific and deep
    char_context = ""
    for c in characters:
        char_context += f"\n- {c['name']}: {c.get('personality', '')}. "
        if c.get('speech_style'):
            char_context += f"Speech style: {c['speech_style']}. "
        if c.get('appearance'):
            # Just first sentence for context, not the full description
            first_sentence = c['appearance'].split('.')[0]
            char_context += f"Appearance: {first_sentence}."

    prompt = f"""For the {category} franchise "{franchise_name}", suggest 8 "Did You Know?" topics \
that would make great 45-60 second Shorts.

CHARACTER DETAILS (use these to craft specific, deep topics — not surface-level):
{char_context}

Franchise iconic elements: {iconic_elements}

Each topic MUST:
- Involve 1-2 of the available characters by name
- Contain the ACTUAL surprising fact (not just "something interesting about X")
- Have a hook that would make someone stop scrolling on TikTok
- Be specific enough that someone could write a script from just the title + hook
- Focus on: plot twists, hidden lore, character backstories, moral dilemmas, easter eggs, \
developer secrets, cut content, or fan theories that most casual fans DON'T know

BAD example: "Joel's Past" — too vague
GOOD example: "Joel Was a Hunter Who Killed Innocent People Before Meeting Ellie" — specific, surprising

Return as a JSON object with key "topics" containing an array of objects, each with:
- "title": Short topic title (5-10 words, contains the specific fact)
- "hook": A one-sentence hook that would grab attention (written as if the character is saying it to camera)
- "characters": Array of character names involved (must match names above exactly)
- "category": One of "plot_twist", "backstory", "easter_egg", "moral_dilemma", "dev_secret", "cut_content", "fan_theory", "lore" """

    return FRANCHISE_SYSTEM, prompt


def script_generation(
    topic_title: str,
    topic_hook: str,
    franchise_name: str,
    visual_aesthetic: str,
    iconic_elements: str,
    characters: list[dict],
) -> tuple[str, str]:
    """Generate a full script with Veo 3 R2V prompts per scene."""
    # Build rich character descriptions including appearance + outfit for Veo 3 prompts
    char_descriptions = ""
    for c in characters:
        char_descriptions += f"\n\n**{c['name']}:**"
        char_descriptions += f"\n  Personality: {c.get('personality', 'unknown')}"
        char_descriptions += f"\n  Speech style: {c.get('speech_style', 'natural')}"
        if c.get('appearance'):
            char_descriptions += f"\n  Appearance: {c['appearance']}"
        if c.get('outfit'):
            char_descriptions += f"\n  Outfit: {c['outfit']}"

    prompt = f"""Write a 7-8 scene script for a 45-55 second Short about:

Topic: {topic_title}
Hook: {topic_hook}
Franchise: {franchise_name}
Visual aesthetic: {visual_aesthetic}
Iconic elements to include in scenes: {iconic_elements}

CHARACTERS (use their appearance and outfit details in Veo 3 prompts):
{char_descriptions}

SCRIPT RULES (critical):
- Each scene: max 15-17 words of dialogue
- The visible character MUST be the speaker (no off-screen narration)
- Scene 1: ALL characters together facing camera (hook scene). One character delivers the hook.
- Last scene: ALL characters together (bookend/closer)
- Middle scenes: alternate between characters — each speaks from their own perspective
- Every scene must include 2-3 franchise-specific visual elements from the iconic elements list
- Vary camera angle per scene: close-up, medium shot, low angle, high angle, dutch angle, over-shoulder
- Each character speaks in their own voice/personality
- Strong facial expressions per scene (angry, haunted, scared, determined — never neutral)

DYNAMIC BACKGROUND RULES (critical — makes scenes visually engaging):
- When a character SPEAKS ABOUT another character, that other character MUST be visible in the \
background or nearby in the scene. Example: if Ranni talks about Marika, Marika should be visible \
in the background (shattered on the Erdtree, or as a statue, or as a vision).
- When a character SPEAKS ABOUT an event, the environment must visually depict that event. \
Example: if Joel talks about the hospital massacre, the background shows a destroyed operating room \
with blood and bullet holes — not a generic dark room.
- The background should TELL THE STORY visually, not just be a setting. Every background element \
should relate to what the character is saying in that moment.
- Use visual contrasts: the speaker in the foreground is composed/speaking, the background shows \
the chaos/beauty/horror they're describing.

VEO 3 PROMPT RULES (critical — each scene must include a ready-to-paste Veo 3 prompt):
- The speaking character's reference image will be uploaded as an "ingredient" in Veo 3 R2V mode
- The Veo 3 prompt must describe the FULL scene as a cohesive paragraph — speaker in foreground \
with appearance and outfit, background characters/events/environments with franchise elements, \
expression, and dialogue all in one flowing description
- IMPORTANT: When background characters appear, describe them briefly but specifically — their \
appearance, what they're doing, their position relative to the speaker. Veo 3 will attempt to \
render them from the text description.
- Use this structure for each veo3_prompt:
  "[Camera angle] of [speaker appearance + outfit] in the foreground. [Background: other characters \
acting out or reacting + environment with franchise iconic elements]. [Expression/body language]. \
[Speaker] says in [voice direction], \\"[dialogue]\\" No background music. Photorealistic, 9:16 \
vertical, [scene-specific lighting]."
- The lighting must be SPECIFIC to the scene mood (not generic "cinematic lighting") — examples: \
"harsh cold fluorescent hospital lighting", "warm golden-hour side light", "cold blue overcast \
natural light", "orange fire glow mixed with cold blue lab lighting"
- Include speaker's key visual details (hair, beard, outfit) in EVERY prompt even though the \
reference image is uploaded — this reinforces consistency

Return as a JSON object with:
- "title": YouTube title (under 60 chars, includes franchise name, uses emoji)
- "tiktok_caption": TikTok caption with hashtags
- "instagram_caption": Instagram caption with hashtags
- "youtube_description": YouTube description (2-3 lines + hashtags)
- "youtube_tags": Array of tag strings
- "scenes": Array of scene objects, each with:
  - "scene_number": integer (1-8)
  - "character_name": who speaks (must EXACTLY match a character name from above)
  - "dialogue": what they say (max 15-17 words)
  - "expression": specific facial expression with micro-details (brow, jaw, eyes)
  - "environment": detailed environment description with franchise elements
  - "camera_angle": shot type
  - "voice_direction": how to deliver the line (tone, emotion, pacing)
  - "veo3_prompt": COMPLETE ready-to-paste Veo 3 R2V prompt as described above. Must be a \
single cohesive paragraph with ALL details filled in. No brackets, no placeholders."""

    return SCRIPT_SYSTEM, prompt
