DROP DATABASE IF EXISTS indexcraft_meta;
CREATE DATABASE indexcraft_meta;
USE indexcraft_meta;

CREATE TABLE analysis_runs (
  run_id      INT AUTO_INCREMENT PRIMARY KEY,
  db_type     VARCHAR(20)  NOT NULL,
  db_name     VARCHAR(100) NOT NULL,
  query_text  TEXT         NOT NULL,
  baseline_ms DECIMAL(10,2),
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE problems (
  problem_id INT AUTO_INCREMENT PRIMARY KEY,
  run_id     INT NOT NULL,
  rule_code  VARCHAR(10) NOT NULL,
  message    TEXT NOT NULL,
  severity   VARCHAR(10),
  FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE suggestions (
  suggestion_id INT AUTO_INCREMENT PRIMARY KEY,
  run_id        INT NOT NULL,
  problem_id    INT NULL,
  ddl_text      TEXT NOT NULL,
  reason        TEXT,
  rank_no       INT,
  FOREIGN KEY (run_id)     REFERENCES analysis_runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (problem_id) REFERENCES problems(problem_id)  ON DELETE SET NULL
);

CREATE TABLE test_results (
  result_id        INT AUTO_INCREMENT PRIMARY KEY,
  suggestion_id    INT NOT NULL UNIQUE,
  before_ms        DECIMAL(10,2),
  after_ms         DECIMAL(10,2),
  rows_before      BIGINT,
  rows_after       BIGINT,
  insert_before_ms DECIMAL(10,2),
  insert_after_ms  DECIMAL(10,2),
  index_size_kb    INT,
  net_benefit_ms   DECIMAL(10,2),
  verdict          VARCHAR(20),
  tested_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (suggestion_id) REFERENCES suggestions(suggestion_id) ON DELETE CASCADE
);

CREATE TABLE reports (
  report_id   INT AUTO_INCREMENT PRIMARY KEY,
  run_id      INT NOT NULL UNIQUE,
  report_text LONGTEXT NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id) ON DELETE CASCADE
);
