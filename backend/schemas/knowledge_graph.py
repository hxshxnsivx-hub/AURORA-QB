"""Pydantic schemas for knowledge graph operations"""

from pydantic import BaseModel
from typing import List, Dict, Any
from uuid import UUID


class PrerequisiteCreateRequest(BaseModel):
    """Schema for creating prerequisite relationship"""
    concept_id: UUID
    prerequisite_id: UUID
    strength: float = 1.0


class ConceptQuestionsResponse(BaseModel):
    """Schema for concept questions response"""
    concept_id: UUID
    question_count: int
    questions: List[Dict[str, Any]]


class PrerequisiteResponse(BaseModel):
    """Schema for prerequisite response"""
    concept_id: str
    concept_name: str
    strength: float


class WeakConceptResponse(BaseModel):
    """Schema for weak concept with strong prerequisites"""
    concept_id: str
    concept_name: str
    mastery_level: float
    avg_prereq_mastery: float
    prerequisite_count: int


class GraphNode(BaseModel):
    """Schema for graph node"""
    id: str
    name: str
    importance: float


class GraphEdge(BaseModel):
    """Schema for graph edge"""
    source: str
    target: str
    strength: float


class GraphVisualizationResponse(BaseModel):
    """Schema for graph visualization"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
