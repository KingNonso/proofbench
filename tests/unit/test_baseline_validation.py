from scripts.validate_baseline import coverage_problems


def test_visible_tests_arm_does_not_satisfy_direct_review_baseline() -> None:
    problems = coverage_problems(["baseline_visible_tests"], [])

    assert problems[0].startswith("missing required baseline_direct_review arm")
