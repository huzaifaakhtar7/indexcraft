USE indexcraft_meta;

SELECT * FROM analysis_runs;

SELECT r.run_id, r.query_text, p.rule_code, p.severity, p.message
FROM analysis_runs r
JOIN problems p ON p.run_id = r.run_id
ORDER BY r.run_id, p.problem_id;

SELECT p.rule_code,
       COUNT(*) AS cases,
       AVG(t.before_ms / NULLIF(t.after_ms, 0)) AS avg_speedup
FROM problems p
JOIN suggestions s ON s.problem_id = p.problem_id
JOIN test_results t ON t.suggestion_id = s.suggestion_id
GROUP BY p.rule_code
ORDER BY avg_speedup DESC;

SELECT r.run_id, r.db_type, r.created_at,
       t.before_ms, t.after_ms, t.verdict
FROM analysis_runs r
JOIN suggestions s ON s.run_id = r.run_id
JOIN test_results t ON t.suggestion_id = s.suggestion_id
ORDER BY r.created_at DESC
LIMIT 10;

SELECT t.verdict, COUNT(*) AS total
FROM test_results t
GROUP BY t.verdict;
