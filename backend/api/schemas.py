from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class HealthResponse(BaseModel):
    status: str
    message: str


class ConnectRequest(BaseModel):
    db_type: Literal["mysql", "postgres", "sqlite"]
    host: str = "localhost"
    port: Optional[int] = Field(None, ge=1, le=65535)
    user: Optional[str] = None
    password: SecretStr = SecretStr("")
    database: str = Field(..., min_length=1, description="Database name, or the .db file path for SQLite")
    schema_name: Optional[str] = Field(None, description="PostgreSQL schema (default: public)")


class TableInfo(BaseModel):
    name: str
    rows: int


class ConnectResponse(BaseModel):
    session_id: str
    db_type: str
    database: str
    tables: list[TableInfo]


class SessionRequest(BaseModel):
    session_id: str


class AnalyzeRequest(BaseModel):
    session_id: str
    query: str = Field(..., min_length=1)


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    table: str
    access: str
    access_label: str
    index_used: Optional[str] = None
    rows_examined: int
    full_scan: bool
    filesort: bool


class Problem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    problem_id: Optional[int] = None
    rule_code: str
    severity: str
    table: Optional[str] = None
    title: str
    message: str
    columns: list[str] = []
    drop_sql: Optional[str] = None


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    suggestion_id: int
    rank: int
    kind: str
    table: str
    columns: list[str]
    index_name: str
    ddl: str
    rewritten_query: Optional[str] = None
    reason: str
    rule_code: Optional[str] = None


class AnalyzeResponse(BaseModel):
    run_id: int
    report_id: Optional[int] = None
    db_type: str
    database: str
    query: str
    rows_examined: int
    plan: list[PlanStep]
    problems: list[Problem]
    suggestions: list[Suggestion]
    notes: list[str]


class RunTestRequest(BaseModel):
    session_id: str
    suggestion_id: int
    read_share: float = Field(0.9, ge=0, le=1, description="Share of reads in the workload (0 to 1)")
    runs: int = Field(5, ge=1, le=20)


class RunTestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: int
    suggestion_id: int
    report_id: Optional[int] = None
    ddl: str
    query_after: str
    before_ms: float
    after_ms: float
    before_timings: list[float]
    after_timings: list[float]
    rows_before: int
    rows_after: int
    plan_before: str
    plan_after: str
    insert_rows: int
    insert_before_ms: float
    insert_after_ms: float
    index_size_kb: int
    read_share: float
    write_share: float
    read_saving_ms: float
    write_penalty_ms_per_row: float
    read_gain_pct: float
    write_loss_pct: float
    speedup: Optional[float] = None
    net_benefit_ms: float
    verdict: str


class ApplyRequest(BaseModel):
    session_id: str
    suggestion_id: int
    confirm: bool = False


class ApplyResponse(BaseModel):
    applied: bool
    sql: str
    rewritten_query: Optional[str] = None
    message: str


class OkResponse(BaseModel):
    ok: bool
    message: str
