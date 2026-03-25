"""Pydantic models for database entities and API responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Franchise ---
class FranchiseBase(BaseModel):
    id: str
    name: str
    franchise_group: str
    category: str


class FranchiseCreate(FranchiseBase):
    config_json: str


class Franchise(FranchiseBase):
    config_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Asset ---
class AssetBase(BaseModel):
    id: str
    franchise_id: str
    asset_type: str
    archetype_id: Optional[str] = None


class Asset(AssetBase):
    status: str = "pending"
    is_narrator: bool = False
    model_dir: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Topic ---
class TopicBase(BaseModel):
    id: str
    franchise_id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None


class Topic(TopicBase):
    freshness: str = "evergreen"
    score: float = 0
    score_breakdown_json: Optional[str] = None
    sources_json: Optional[str] = None
    characters_needed_json: Optional[str] = None
    asset_status: str = "unknown"
    suggested_hook: Optional[str] = None
    status: str = "discovered"
    narrator_archetype: Optional[str] = None
    closer_style: Optional[str] = None
    queued_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Script ---
class Script(BaseModel):
    id: int
    topic_id: str
    script_json: str
    word_count: Optional[int] = None
    total_duration_seconds: Optional[float] = None
    similarity_score: Optional[float] = None
    status: str = "generated"
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Video ---
class Video(BaseModel):
    id: int
    topic_id: str
    script_id: int
    franchise_id: str
    narrator_archetype: Optional[str] = None
    youtube_video_id: Optional[str] = None
    tiktok_video_id: Optional[str] = None
    instagram_video_id: Optional[str] = None
    facebook_video_id: Optional[str] = None
    video_path: Optional[str] = None
    long_form_outline_path: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags_json: Optional[str] = None
    closer_style: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Analytics ---
class AnalyticsSnapshot(BaseModel):
    id: int
    video_id: int
    snapshot_type: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    avg_view_duration_pct: Optional[float] = None
    click_through_rate: Optional[float] = None
    subscribers_gained: int = 0
    traffic_sources_json: Optional[str] = None
    collected_at: datetime

    model_config = {"from_attributes": True}


# --- Pipeline Run ---
class PipelineRun(BaseModel):
    id: int
    topic_id: Optional[str] = None
    status: str = "running"
    current_step: Optional[str] = None
    steps_log_json: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Settings ---
class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingsResponse(BaseModel):
    settings: dict[str, str]
