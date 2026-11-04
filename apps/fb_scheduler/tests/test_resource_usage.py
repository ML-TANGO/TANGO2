"""Unit tests for scheduler/resource_usage.py::calculate_collector_usage."""


def _collect(**kw):
    row = {"start_datetime": "2026-08-03 07:38:10", "end_datetime": None,
           "cpu_allocate": 4, "ram_allocate": 80}
    row.update(kw)
    return row


def test_running_collector_counts_its_instance_bundle():
    from scheduler.resource_usage import calculate_collector_usage
    assert calculate_collector_usage(_collect()) == (4, 80, 0)


def test_collector_whose_instance_was_deleted_counts_as_zero():
    # 인스턴스가 지워지면 get_collect_list 의 LEFT JOIN 값이 None 이다 — TypeError 로 스케줄러 틱
    # 전체가 버려지던 장애(서빙 2026-09-29). 0 으로 본다.
    from scheduler.resource_usage import calculate_collector_usage
    assert calculate_collector_usage(_collect(cpu_allocate=None, ram_allocate=None)) == (0, 0, 0)


def test_finished_or_unstarted_collector_uses_nothing():
    from scheduler.resource_usage import calculate_collector_usage
    assert calculate_collector_usage(_collect(end_datetime="2026-08-04 00:00:00")) == (0, 0, 0)
    assert calculate_collector_usage(_collect(start_datetime=None)) == (0, 0, 0)
