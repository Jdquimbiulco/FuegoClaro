import numpy as np
import pytest
from app.domain import fire_events as events


@pytest.mark.parametrize("seed", range(5))
def test_single_point_dbscan_matches_original_graph_without_materializing_edges(monkeypatch, seed):
    rng = np.random.default_rng(seed)
    lat = rng.uniform(-.06, .06, 120)
    lon = rng.uniform(-78.06, -77.94, 120)
    days = rng.integers(1, 6, len(lat))
    left, right = events._neighbour_pairs(lat, lon, days, 2., 2)
    adjacency = [set() for _ in lat]
    for a, b in zip(left, right):
        adjacency[a].add(b)
        adjacency[b].add(a)
    expected = np.full(len(lat), -1)
    label = 0
    for start in range(len(lat)):
        if expected[start] != -1:
            continue
        queue = [start]
        while queue:
            point = queue.pop()
            if expected[point] != -1:
                continue
            expected[point] = label
            queue.extend(adjacency[point])
        label += 1
    def no_all_edges(*args, **kwargs):
        raise AssertionError("min_points=1 must not retain all candidate pairs or adjacency sets")
    monkeypatch.setattr(events, "_neighbour_pairs", no_all_edges)
    actual = events._dbscan_st(lat, lon, days, 2., 2, 1)
    np.testing.assert_array_equal(actual, expected)
