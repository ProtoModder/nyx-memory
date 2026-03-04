#!/usr/bin/env python3
"""
Nyx Memory System - Comprehensive Benchmark Suite
==================================================
Tests QMD standalone vs unified system with detailed scoring.
"""

import time
import sys
import json
import statistics
from pathlib import Path

# Add memory to path
sys.path.insert(0, '/home/node/.openclaw/memory')

# Results storage
results = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "tests": {},
    "scores": {},
    "breakdown": {}
}

def measure(func, iterations=5):
    """Measure function execution time with multiple iterations."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append((time.perf_counter() - start) * 1000)  # ms
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times),
        "iterations": iterations
    }

# Import components
from actr_ranker import search_qmd, unified_search, calculate_activation, load_pagerank_scores, clear_cache

# Clear cache at start to ensure fair cold comparison
clear_cache()

# Test queries covering different domains - with random suffix to prevent caching
import random
import string

def make_unique_query(base_query, run_id):
    """Add random suffix to make query unique per run (prevents cache)"""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{base_query} {run_id}_{suffix}"

# Generate unique queries for this run
run_id = random.randint(10000, 99999)
test_queries = [
    make_unique_query("memory", run_id),
    make_unique_query("tts voice", run_id),
    make_unique_query("workflow automation", run_id),
    make_unique_query("cognitive architecture", run_id),
    make_unique_query("puppeteer stealth", run_id),
    make_unique_query("docker container", run_id),
    make_unique_query("youtube transcript", run_id),
    make_unique_query("pdf extraction", run_id),
    make_unique_query("ollama model", run_id),
    make_unique_query("weather cron", run_id)
]

print("=" * 60)
print("NYX MEMORY SYSTEM - COMPREHENSIVE BENCHMARK")
print(f"Run ID: {run_id} (unique queries for fair comparison)")
print("=" * 60)
print()

# ============================================================================
# TEST 1: QMD Standalone
# ============================================================================
print("[1/7] Testing QMD Standalone...")

qmd_results = {}
for query in test_queries:
    qmd_results[query] = measure(lambda q=query: search_qmd(q, max_results=10))

results["tests"]["qmd_standalone"] = qmd_results

avg_qmd = statistics.mean([r["mean"] for r in qmd_results.values()])
print(f"  Average: {avg_qmd:.1f}ms")

# ============================================================================
# TEST 2: Unified Search (Full System)
# ============================================================================
print("[2/7] Testing Unified Search...")

unified_results = {}
for query in test_queries:
    unified_results[query] = measure(lambda q=query: unified_search(q, max_results=10))

results["tests"]["unified_search"] = unified_results

avg_unified = statistics.mean([r["mean"] for r in unified_results.values()])
print(f"  Average: {avg_unified:.1f}ms")

# ============================================================================
# TEST 3: Activation Calculation
# ============================================================================
print("[3/7] Testing Activation Calculation...")

from actr_ranker import load_activation_log

activation_results = []
act_log = load_activation_log()
if act_log and "access_log" in act_log:
    for slug in list(act_log["access_log"].keys())[:10]:
        activation_results.append(measure(lambda s=slug: calculate_activation(s)))

if activation_results:
    avg_activation = statistics.mean([r["mean"] for r in activation_results])
else:
    avg_activation = 0

results["tests"]["activation"] = {"mean": avg_activation}
print(f"  Average: {avg_activation:.1f}ms")

# ============================================================================
# TEST 4: PageRank Loading
# ============================================================================
print("[4/7] Testing PageRank Loading...")

pagerank_results = measure(lambda: load_pagerank_scores())
results["tests"]["pagerank"] = pagerank_results

print(f"  Average: {pagerank_results['mean']:.1f}ms")

# ============================================================================
# TEST 5: Tag Loading (from files)
# ============================================================================
print("[5/7] Testing Tag Graph Loading...")

# Load tags from all problem files
problems_dir = Path("/home/node/.openclaw/workspace/memory/problems")
all_problem_tags = {}

def load_all_tags():
    for pf in problems_dir.glob("*.md"):
        slug = pf.stem
        content = pf.read_text()
        tags = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('**Tags:**'):
                tags_str = line.replace('**Tags:**', '').strip()
                tags = [t.strip().rstrip(',') for t in tags_str.split() if t.strip()]
                break
        all_problem_tags[slug] = tags

tag_results = measure(load_all_tags)
results["tests"]["tag_graph"] = tag_results

print(f"  Loaded {len(all_problem_tags)} problem tags")
print(f"  Average: {tag_results['mean']:.1f}ms")

# ============================================================================
# TEST 6: Cache Performance
# ============================================================================
print("[6/7] Testing Cache Performance...")

# Generate unique queries for cold/warm test
cold_query = make_unique_query("cache test", run_id)
warm_query = "memory"  # Use known query that will be cached

# First call (cold) - unique query, no cache
cold_results = measure(lambda q=cold_query: unified_search(q, max_results=5), iterations=3)

# Pre-cache the warm query first
unified_search(warm_query, max_results=5)

# Second call (warm - should be cached)
_warm_results = measure(lambda q=warm_query: unified_search(q, max_results=5), iterations=3)

results["tests"]["cache_cold"] = cold_results
results["tests"]["cache_warm"] = _warm_results

print(f"  Cold: {cold_results['mean']:.1f}ms")
print(f"  Warm: {_warm_results['mean']:.1f}ms")
print(f"  Speedup: {cold_results['mean']/_warm_results['mean']:.1f}x")

# ============================================================================
# TEST 7: Recall Accuracy
# ============================================================================
print("[7/7] Testing Recall Accuracy...")

recall_tests = [
    ("tts", ["tts", "voice", "piper"]),
    ("memory", ["memory", "actr", "activation"]),
    ("puppeteer", ["puppeteer", "stealth", "browser"]),
    ("youtube", ["youtube", "transcript", "video"]),
    ("docker", ["docker", "container", "rocM"]),
    ("pdf", ["pdf", "extraction", "llava"]),
]

recall_correct = 0
recall_total = 0

for query, expected_tags in recall_tests:
    unified = unified_search(query, max_results=10)
    found_slugs = [r["slug"] for r in unified]
    
    # Check if any result has expected tags
    matches = 0
    for slug in found_slugs:
        if slug in all_problem_tags:
            tags_for_problem = all_problem_tags[slug]
            if any(et.lower() in " ".join(tags_for_problem).lower() for et in expected_tags):
                matches += 1
    
    if matches > 0:
        recall_correct += 1
    recall_total += 1

recall_accuracy = (recall_correct / recall_total) * 100 if recall_total > 0 else 0
results["tests"]["recall"] = {"correct": recall_correct, "total": recall_total, "accuracy": recall_accuracy}

print(f"  Recall: {recall_correct}/{recall_total} ({recall_accuracy:.0f}%)")

# ============================================================================
# SCORING SYSTEM (0-40 points)
# ============================================================================
print()
print("=" * 60)
print("SCORING BREAKDOWN (0-40 points)")
print("=" * 60)

scores = {}

# Speed Score (0-10 points)
# Lower is better
speed_score = 0
if avg_unified < 100:
    speed_score = 10
elif avg_unified < 300:
    speed_score = 8
elif avg_unified < 500:
    speed_score = 6
elif avg_unified < 700:
    speed_score = 4
elif avg_unified < 1000:
    speed_score = 2
else:
    speed_score = 1

scores["speed"] = speed_score
print(f"  Speed Score (10 max): {speed_score}/10 ({avg_unified:.0f}ms)")

# Cache Efficiency (0-5 points)
cache_speedup = cold_results['mean'] / _warm_results['mean'] if _warm_results['mean'] > 0 else 1
cache_score = min(5, int(cache_speedup))
scores["cache"] = cache_score
print(f"  Cache Score (5 max): {cache_score}/5 ({cache_speedup:.1f}x speedup)")

# Component Performance (0-5 points)
component_score = 0
if pagerank_results['mean'] < 1:
    component_score += 2
if tag_results['mean'] < 10:
    component_score += 2
if avg_activation < 1:
    component_score += 1

scores["components"] = component_score
print(f"  Components Score (5 max): {component_score}/5")

# Recall Accuracy (0-10 points)
recall_score = int(recall_accuracy / 10)
scores["recall"] = recall_score
print(f"  Recall Score (10 max): {recall_score}/10 ({recall_accuracy:.0f}%)")

# Overhead Score (0-5 points)
# How much slower is unified vs QMD alone?
overhead = ((avg_unified - avg_qmd) / avg_qmd) * 100 if avg_qmd > 0 else 0
if overhead < 0:
    overhead_score = 5  # Unified is faster!
elif overhead < 5:
    overhead_score = 4
elif overhead < 10:
    overhead_score = 3
elif overhead < 20:
    overhead_score = 2
else:
    overhead_score = 1

scores["overhead"] = overhead_score
print(f"  Overhead Score (5 max): {overhead_score}/5 ({overhead:+.1f}%)")

# Consistency Score (0-5 points)
# Based on standard deviation
qmd_stdev = statistics.mean([r["stdev"] for r in qmd_results.values()])
if qmd_stdev < 10:
    consistency_score = 5
elif qmd_stdev < 30:
    consistency_score = 4
elif qmd_stdev < 50:
    consistency_score = 3
elif qmd_stdev < 100:
    consistency_score = 2
else:
    consistency_score = 1

scores["consistency"] = consistency_score
print(f"  Consistency Score (5 max): {consistency_score}/5 (stdev: {qmd_stdev:.1f}ms)")

# ============================================================================
# FINAL SCORE
# ============================================================================
total_score = sum(scores.values())
max_score = 40

print()
print("=" * 60)
print(f"FINAL SCORE: {total_score}/{max_score}")
print("=" * 60)

# Grade
if total_score >= 36:
    grade = "A+"
elif total_score >= 32:
    grade = "A"
elif total_score >= 28:
    grade = "B"
elif total_score >= 24:
    grade = "C"
elif total_score >= 20:
    grade = "D"
else:
    grade = "F"

print(f"Grade: {grade}")
print()

# Summary
print("SUMMARY:")
print(f"  QMD Standalone: {avg_qmd:.0f}ms")
print(f"  Unified Search: {avg_unified:.0f}ms")
print(f"  Overhead: {overhead:+.1f}%")
print(f"  Cache Speedup: {cache_speedup:.1f}x")
print(f"  Recall: {recall_accuracy:.0f}%")
print(f"  Problems Indexed: {len(all_problem_tags)}")

results["scores"] = scores
results["total_score"] = total_score
results["max_score"] = max_score
results["grade"] = grade

# Save results
output_path = Path("/home/node/.openclaw/memory/benchmark_results.json")
with open(output_path, "w") as f:
    json.dump(results, f, indent=2)

print()
print(f"Results saved to: {output_path}")
