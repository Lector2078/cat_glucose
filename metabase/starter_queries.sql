-- Daily trend by cat
SELECT
  c.name AS cat_name,
  DATE_TRUNC('day', r.reading_at) AS day_bucket,
  AVG(r.glucose_value) AS avg_glucose
FROM glucose_readings r
JOIN cats c ON c.id = r.cat_id
GROUP BY c.name, DATE_TRUNC('day', r.reading_at)
ORDER BY day_bucket DESC, c.name;

-- 7-day moving average by cat
SELECT
  c.name AS cat_name,
  DATE_TRUNC('day', r.reading_at) AS day_bucket,
  AVG(AVG(r.glucose_value)) OVER (
    PARTITION BY c.name
    ORDER BY DATE_TRUNC('day', r.reading_at)
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS moving_avg_7d
FROM glucose_readings r
JOIN cats c ON c.id = r.cat_id
GROUP BY c.name, DATE_TRUNC('day', r.reading_at)
ORDER BY day_bucket DESC, c.name;

-- 30-day moving average by cat
SELECT
  c.name AS cat_name,
  DATE_TRUNC('day', r.reading_at) AS day_bucket,
  AVG(AVG(r.glucose_value)) OVER (
    PARTITION BY c.name
    ORDER BY DATE_TRUNC('day', r.reading_at)
    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
  ) AS moving_avg_30d
FROM glucose_readings r
JOIN cats c ON c.id = r.cat_id
GROUP BY c.name, DATE_TRUNC('day', r.reading_at)
ORDER BY day_bucket DESC, c.name;

-- Min/Max/Median by week
SELECT
  c.name AS cat_name,
  DATE_TRUNC('week', r.reading_at) AS week_bucket,
  MIN(r.glucose_value) AS min_glucose,
  MAX(r.glucose_value) AS max_glucose,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.glucose_value) AS median_glucose
FROM glucose_readings r
JOIN cats c ON c.id = r.cat_id
GROUP BY c.name, DATE_TRUNC('week', r.reading_at)
ORDER BY week_bucket DESC, c.name;

-- Time-of-day pattern distribution
SELECT
  c.name AS cat_name,
  EXTRACT(HOUR FROM r.reading_at) AS hour_of_day,
  AVG(r.glucose_value) AS avg_glucose,
  COUNT(*) AS sample_count
FROM glucose_readings r
JOIN cats c ON c.id = r.cat_id
GROUP BY c.name, EXTRACT(HOUR FROM r.reading_at)
ORDER BY c.name, hour_of_day;
