from medeval.reporter.aggregator import build_report

from factories import make_case_result


def test_run_report_groups_final_outcomes_by_case_type():
    passed = make_case_result("case_passed")
    passed.case.case_type = "医学诊疗类"
    failed = make_case_result("case_failed", release_passed=False)
    failed.case.case_type = "医学诊疗类"
    uncategorized = make_case_result("case_uncategorized")

    report = build_report(
        "case_type_summary",
        [passed, failed, uncategorized],
        adapter_type="stub",
    )

    assert report.by_case_type["医学诊疗类"]["total"] == 2
    assert report.by_case_type["医学诊疗类"]["passed"] == 1
    assert report.by_case_type["未分类"]["total"] == 1
    assert report.by_case_type["未分类"]["passed"] == 1
