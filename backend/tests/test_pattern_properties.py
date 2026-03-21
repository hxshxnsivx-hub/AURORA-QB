"""Property-based tests for Pattern Miner Agent - Properties 18-23"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

from agents.pattern_miner_agent import PatternMinerAgent


# Property 18: Mark Distribution Validity
@given(marks_list=st.lists(st.integers(min_value=1, max_value=12), min_size=1, max_size=100))
@settings(max_examples=30, deadline=None)
def test_property_18_mark_distribution_validity(marks_list, db_session):
    """Property 18: Mark distribution frequencies sum to 1.0"""
    agent = PatternMinerAgent(db_session)
    questions = [Mock(marks=m) for m in marks_list]
    
    dist = agent._calculate_mark_distribution(questions)
    
    assert sum(dist.values()) == pytest.approx(1.0, abs=0.001)
    assert all(0 <= v <= 1 for v in dist.values())


# Property 19: Type Distribution Validity
@given(types_list=st.lists(
    st.sampled_from(["MCQ", "Short Answer", "Long Answer", "Numerical", "True/False"]),
    min_size=1, max_size=100
))
@settings(max_examples=30, deadline=None)
def test_property_19_type_distribution_validity(types_list, db_session):
    """Property 19: Type distribution percentages sum to 1.0"""
    agent = PatternMinerAgent(db_session)
    questions = [Mock(type=Mock(value=t)) for t in types_list]
    
    dist = agent._calculate_type_distribution(questions)
    
    assert sum(dist.values()) == pytest.approx(1.0, abs=0.001)
    assert all(0 <= v <= 1 for v in dist.values())


# Property 20: Topic Weight Validity
@given(topic_ids=st.lists(st.uuids(), min_size=1, max_size=50))
@settings(max_examples=30, deadline=None)
def test_property_20_topic_weight_validity(topic_ids, db_session):
    """Property 20: Topic weights sum to 1.0"""
    agent = PatternMinerAgent(db_session)
    questions = [Mock(topic_id=tid) for tid in topic_ids]
    
    weights = agent._calculate_topic_weights(questions)
    
    if weights:  # Only if there are topics
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.001)
        assert all(0 <= v <= 1 for v in weights.values())


# Property 21: Difficulty Distribution Validity
@given(
    marks=st.integers(min_value=1, max_value=12),
    difficulties=st.lists(
        st.sampled_from(["Easy", "Medium", "Hard"]),
        min_size=1, max_size=50
    )
)
@settings(max_examples=30, deadline=None)
def test_property_21_difficulty_distribution_validity(marks, difficulties, db_session):
    """Property 21: Difficulty distribution per mark category sums to 1.0"""
    agent = PatternMinerAgent(db_session)
    questions = [Mock(marks=marks, difficulty=Mock(value=d)) for d in difficulties]
    
    dist = agent._calculate_difficulty_by_marks(questions)
    
    if str(marks) in dist:
        mark_dist = dist[str(marks)]
        assert sum(mark_dist.values()) == pytest.approx(1.0, abs=0.001)
        assert all(0 <= v <= 1 for v in mark_dist.values())


# Property 23: Pattern Aggregation Commutativity
@given(
    marks_list1=st.lists(st.integers(min_value=1, max_value=12), min_size=5, max_size=20),
    marks_list2=st.lists(st.integers(min_value=1, max_value=12), min_size=5, max_size=20)
)
@settings(max_examples=20, deadline=None)
def test_property_23_pattern_aggregation_commutativity(marks_list1, marks_list2, db_session):
    """Property 23: Pattern aggregation order doesn't matter"""
    agent = PatternMinerAgent(db_session)
    
    # Aggregate in order 1 -> 2
    questions_12 = [Mock(marks=m) for m in marks_list1 + marks_list2]
    dist_12 = agent._calculate_mark_distribution(questions_12)
    
    # Aggregate in order 2 -> 1
    questions_21 = [Mock(marks=m) for m in marks_list2 + marks_list1]
    dist_21 = agent._calculate_mark_distribution(questions_21)
    
    # Results should be identical
    assert dist_12.keys() == dist_21.keys()
    for key in dist_12.keys():
        assert dist_12[key] == pytest.approx(dist_21[key], abs=0.001)
