from navigation_analyzer.io.rosbag2 import _TransformEvent, compute_tf_ages_for_times


def _tf(stamp_t: float | None) -> _TransformEvent:
    return _TransformEvent(t=stamp_t or 0.0, parent="map", child="odom", x=0.0, y=0.0, yaw=0.0, stamp_t=stamp_t)


def test_chain_age_uses_stalest_link():
    map_to_odom = [_tf(0.0), _tf(2.0)]   # latest map→odom stamp = 2.0
    odom_to_base = [_tf(0.0), _tf(0.5), _tf(1.5), _tf(2.95), _tf(3.0)]  # latest at 3.0
    ages = compute_tf_ages_for_times([3.0], map_to_odom, odom_to_base, direct_map_to_base=[])
    # chain age = 3.0 - min(2.0, 3.0) = 1.0 (map→odom is the stale link)
    assert ages[3.0] == 1.0


def test_age_zero_when_chain_is_fresh():
    map_to_odom = [_tf(5.0)]
    odom_to_base = [_tf(5.0)]
    ages = compute_tf_ages_for_times([5.0], map_to_odom, odom_to_base, direct_map_to_base=[])
    assert ages[5.0] == 0.0


def test_age_is_none_when_a_link_is_missing():
    map_to_odom = [_tf(1.0)]
    odom_to_base: list = []
    ages = compute_tf_ages_for_times([2.0], map_to_odom, odom_to_base, direct_map_to_base=[])
    assert ages[2.0] is None


def test_age_is_none_before_any_tf_messages():
    map_to_odom = [_tf(5.0)]
    odom_to_base = [_tf(5.0)]
    ages = compute_tf_ages_for_times([1.0, 4.999, 5.0, 6.0], map_to_odom, odom_to_base, direct_map_to_base=[])
    assert ages[1.0] is None
    assert ages[4.999] is None
    assert ages[5.0] == 0.0
    assert ages[6.0] == 1.0


def test_direct_chain_is_used_when_no_intermediate():
    direct = [_tf(0.0), _tf(2.0)]
    ages = compute_tf_ages_for_times([3.0], map_to_odom=[], odom_to_base=[], direct_map_to_base=direct)
    assert ages[3.0] == 1.0


def test_intermediate_chain_takes_priority_over_direct():
    # If both direct and intermediate exist, intermediate wins (more typical Nav2 setup).
    direct = [_tf(0.0), _tf(0.5)]  # stalest if used
    map_to_odom = [_tf(2.0)]
    odom_to_base = [_tf(2.5)]
    ages = compute_tf_ages_for_times([3.0], map_to_odom, odom_to_base, direct_map_to_base=direct)
    assert ages[3.0] == 1.0  # chain age, not 2.5


def test_transforms_without_stamp_are_ignored():
    map_to_odom = [_tf(None), _tf(1.0)]
    odom_to_base = [_tf(2.0), _tf(None)]
    ages = compute_tf_ages_for_times([3.0], map_to_odom, odom_to_base, direct_map_to_base=[])
    # uses 1.0 (latest valid stamp on map→odom) and 2.0 (latest on odom→base)
    assert ages[3.0] == 2.0  # 3.0 - min(1.0, 2.0)
