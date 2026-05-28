# 카운터 데이터 전송

상위 문서: [센서 데이터 전송](/protocol/data/sensor_data)

## :arrow_up: MQTT Upstream

- topic: {application}/{region_id}/_data/{gateway_id}

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "current_count": 0,
  "accumulated_count": 0
}
```

---

# 카운터 데이터 계산

- 카운터 데이터 유실에 의한 피해를 최소화 하기 위해 다음 데이터를 전송
  - current_count: 하나의 전송 주기동안 감지된 카운트 수
  - accumulated_count: 노드 부팅 후 누적된 카운트 값 (노드에서 매일 0시에 초기화 권장)
- TimescaleDB에 저장되는 경우, 다음 Query를 통해 일별 count 값을 계산
  - 원하는 범위의 데이터 조회
  - 노드가 reset되는 경우 accumulated_count가 0부터 시작하는 점을 이용하여, 직전의 accumulated_count 값보다 작아지는 부분이 있는지 확인
  - 리셋이 발생한 경우 current_count 값을 더해서 카운트 값 계산, 리셋이 발생하지 않은 경우 accumulated_count 값을 통해 카운트 값 계산

```sql
WITH daily_data AS (
    SELECT
        ts,
        site_id,
        sensor_id,
        current_count,
        accumulated_count,
        DATE_TRUNC('day', ts AT TIME ZONE 'Asia/Seoul') AT TIME ZONE 'Asia/Seoul' AS day_start,
        LAG(accumulated_count, 1, accumulated_count) OVER (
            PARTITION BY site_id, sensor_id,
            DATE_TRUNC('day', ts AT TIME ZONE 'Asia/Seoul')
            ORDER BY ts
        ) AS prev_accumulated_count,
        FIRST_VALUE(current_count) OVER (
            PARTITION BY site_id, sensor_id,
            DATE_TRUNC('day', ts AT TIME ZONE 'Asia/Seoul')
            ORDER BY ts
        ) AS first_current_count
    FROM
        counter
    WHERE
        site_id = ?
        AND ts >= ? AND ts < ?
        AND NOT invalid
),
reset_groups AS (
    SELECT
        *,
        SUM(CASE WHEN accumulated_count < prev_accumulated_count THEN 1 ELSE 0 END) OVER (
            PARTITION BY site_id, sensor_id, day_start
            ORDER BY ts
        ) AS reset_group
    FROM
        daily_data
)
SELECT
    site_id,
    sensor_id,
    day_start,
    CASE
        -- 리셋이 발생하지 않은 경우
        WHEN MAX(reset_group) = 0 THEN
             (MAX(accumulated_count) - MIN(accumulated_count)) + MAX(first_current_count)
        -- 리셋이 발생한 경우
        ELSE
             SUM(current_count)
    END AS final_daily_count
FROM
    reset_groups
GROUP BY
    site_id, sensor_id, day_start
ORDER BY
    day_start, site_id, sensor_id
```

## TODO

- 데이터가 많아진다면 SQL 조회 유지
- 요청이 많아진다면 App 접근 방식으로 변경하는 것을 고려
  - 필요에 따라 일별 데이터를 계산해 둘 필요 있음
- 비즈니스 로직이 복잡해진다면 App 접근 방식으로 변경
