from pydantic import BaseModel


# --- Franchises ---

class FranchiseCreate(BaseModel):
    name: str
    category: str = "gaming"


class FranchiseUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    visual_aesthetic: str | None = None
    iconic_elements: str | None = None


class FranchiseResponse(BaseModel):
    id: str
    name: str
    category: str
    visual_aesthetic: str | None = None
    iconic_elements: str | None = None
    created_at: str | None = None


class FranchiseWithCharacters(FranchiseResponse):
    characters: list["CharacterResponse"] = []


# --- Characters ---

class CharacterCreate(BaseModel):
    name: str


class CharacterUpdate(BaseModel):
    name: str | None = None
    appearance: str | None = None
    outfit: str | None = None
    personality: str | None = None
    speech_style: str | None = None
    flow_prompt: str | None = None
    flow_url: str | None = None


class CharacterResponse(BaseModel):
    id: str
    franchise_id: str
    name: str
    appearance: str | None = None
    outfit: str | None = None
    personality: str | None = None
    speech_style: str | None = None
    flow_prompt: str | None = None
    image_path: str | None = None
    flow_url: str | None = None
    created_at: str | None = None


# --- Shorts ---

class ShortCreate(BaseModel):
    franchise_id: str


class ShortUpdate(BaseModel):
    topic: str | None = None
    script_json: str | None = None
    status: str | None = None
    current_step: int | None = None
    upload_metadata_json: str | None = None


class ShortResponse(BaseModel):
    id: int
    franchise_id: str
    franchise_name: str | None = None
    topic: str | None = None
    script_json: str | None = None
    status: str = "draft"
    current_step: int = 1
    upload_metadata_json: str | None = None
    created_at: str | None = None
    published_at: str | None = None
    scenes: list["SceneResponse"] = []


class ShortListItem(BaseModel):
    id: int
    franchise_id: str
    franchise_name: str | None = None
    topic: str | None = None
    status: str = "draft"
    current_step: int = 1
    scene_count: int = 0
    created_at: str | None = None
    published_at: str | None = None


# --- Scenes ---

class SceneUpdate(BaseModel):
    status: str | None = None
    flow_url: str | None = None


class SceneResponse(BaseModel):
    id: int
    short_id: int
    scene_number: int
    character_id: str | None = None
    character_name: str | None = None
    dialogue: str | None = None
    expression: str | None = None
    environment: str | None = None
    veo3_prompt: str | None = None
    flow_url: str | None = None
    status: str = "pending"


# --- Wizard ---

class TopicSelection(BaseModel):
    topic: str
    hook: str
    characters: list[str] = []


class GenerateScriptRequest(BaseModel):
    topic: str
    hook: str
    character_names: list[str] = []


# --- Settings ---

class SettingsUpdate(BaseModel):
    settings: dict[str, str]
