#!/usr/bin/env python3
"""
Tests for ACT-R Unified Memory Ranker

Run with: python3 test_actr_ranker.py
"""

import sys
import os
sys.path.insert(0, '/home/node/.openclaw/memory')

from actr_ranker import (
    load_activation_log,
    load_tag_graph,
    load_pagerank_scores,
    calculate_activation,
    record_access_with_priming,
    unified_search,
    search_qmd,
    WEIGHT_QMD,
    WEIGHT_ACTIVATION,
    WEIGHT_PAGERANK,
    WEIGHT_RELATIONSHIPS,
    BASE_LEVEL
)

def test_weights_sum_to_one():
    """Verify all weights sum to 1.0"""
    total = WEIGHT_QMD + WEIGHT_ACTIVATION + WEIGHT_PAGERANK + WEIGHT_RELATIONSHIPS
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"
    print("✓ Weights sum to 1.0")

def test_activation_log_loads():
    """Verify activation log loads"""
    data = load_activation_log()
    assert "items" in data, "Missing 'items' key"
    assert len(data["items"]) > 0, "No items in activation log"
    print(f"✓ Activation log: {len(data['items'])} items")

def test_tag_graph_loads():
    """Verify tag graph loads"""
    graph = load_tag_graph()
    assert "nodes" in graph, "Missing 'nodes' key"
    assert "edges" in graph, "Missing 'edges' key"
    print(f"✓ Tag graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")

def test_pagerank_loads():
    """Verify PageRank scores load"""
    scores = load_pagerank_scores()
    assert len(scores) > 0, "No PageRank scores"
    print(f"✓ PageRank: {len(scores)} scores")

def test_calculate_activation():
    """Test activation calculation"""
    from datetime import datetime, timezone
    
    # Fresh item
    item = {"access_times": [], "created": datetime.now(timezone.utc).isoformat()}
    act = calculate_activation(item, datetime.now(timezone.utc))
    assert act == BASE_LEVEL, f"Fresh item should have base level {BASE_LEVEL}"
    
    # Accessed item
    item = {
        "access_times": [datetime.now(timezone.utc).isoformat()],
        "created": datetime.now(timezone.utc).isoformat()
    }
    act = calculate_activation(item, datetime.now(timezone.utc))
    assert act > BASE_LEVEL, "Accessed item should have higher activation"
    print(f"✓ Activation calculation works: {act:.3f}")

def test_unified_search_returns_valid_results():
    """Verify unified search returns valid results"""
    queries = ["memory", "tts", "workflow", "puppeteer"]
    
    for q in queries:
        results = unified_search(q, max_results=3)
        assert len(results) > 0, f"No results for query '{q}'"
        
        # Verify result structure
        r = results[0]
        assert "slug" in r, "Missing 'slug'"
        assert "final_score" in r, "Missing 'final_score'"
        assert 0 <= r["final_score"] <= 1, "Score out of range"
        
        # Verify all scores present
        assert "qmd_score" in r, "Missing QMD score"
        assert "activation" in r, "Missing activation score"
        assert "pagerank" in r, "Missing PageRank score"
        assert "exact_bonus" in r, "Missing exact bonus"
        
        print(f"  ✓ Query '{q}': {r['slug']} (score: {r['final_score']:.2f})")
    
    print("✓ Unified search works for all queries")

def test_scores_in_range():
    """Verify all scores are in valid range"""
    results = unified_search("test", max_results=5)
    for r in results:
        for key in ["qmd_score", "activation", "pagerank", "relationships", "exact_bonus", "final_score"]:
            score = r.get(key, 0)
            assert 0 <= score <= 1, f"{key} score {score} out of range"
    print("✓ All scores in valid range [0, 1]")

def test_recall_accuracy():
    """Test recall accuracy on known problems"""
    tests = [
        ("brain memory hopfield", "video-brain-memory-retrieval"),
        ("soar actr cognitive", "video-cognitive-architectures-soar-actr"),
        ("workload prediction", "video-cognitive-workload-prediction"),
        ("openclaw employee", "video-openclaw-fulltime-employee"),
        ("titans llm memory", "video-titans-integrated-llm-memory"),
        ("puppeteer", "puppeteer-stealth-bypass"),
        ("memory ai", "mem0-ai-memory"),
        ("cognitive architecture", "cognitive-architecture-real-time-performance"),
    ]
    
    correct = 0
    for query, expected in tests:
        results = unified_search(query, max_results=3)
        top = results[0]["slug"] if results else "none"
        if expected in top:
            correct += 1
        else:
            print(f"  ✗ '{query}' -> {top} (expected {expected})")
    
    accuracy = correct / len(tests) * 100
    print(f"✓ Recall accuracy: {correct}/{len(tests)} = {accuracy:.0f}%")
    return accuracy >= 70  # Require at least 70% recall

def main():
    print("=== ACT-R Unified Ranker Tests ===\n")
    
    print("1. Weight Validation")
    test_weights_sum_to_one()
    
    print("\n2. Data Loading")
    test_activation_log_loads()
    test_tag_graph_loads()
    test_pagerank_loads()
    
    print("\n3. Core Functions")
    test_calculate_activation()
    
    print("\n4. Search Functionality")
    test_unified_search_returns_valid_results()
    test_scores_in_range()
    
    print("\n5. Recall Accuracy")
    recall_ok = test_recall_accuracy()
    
    print("\n" + "="*40)
    if recall_ok:
        print("ALL TESTS PASSED ✓")
    else:
        print("WARNING: Recall below 70%")
    print("="*40)

if __name__ == "__main__":
    main()
