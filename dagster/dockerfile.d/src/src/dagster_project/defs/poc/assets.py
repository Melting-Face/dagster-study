"""PoC 자산: 호스트 Dagster가 SparkApplication을 트리거해 Iceberg에 적재.

Spark Operator CRD를 제출·폴링하고, driver 로그에서 결과를 회수해
materialization 메타데이터로 남긴다. 재설계의 "호스트 오케스트레이터 →
원격 컴퓨트(Spark on K8s)" 패턴의 최소 실증이다.

주의: 이 자산은 실인프라(kind 클러스터)에 접속하므로 단위 테스트 대상이 아니다
(격리 원칙 — 검증은 라이브 클러스터에서 수행). context class identity 검사 때문에
자산 모듈에서는 `from __future__ import annotations`를 쓰지 않는다.
"""

import re
from pathlib import Path

import yaml

import dagster as dg
from dagster_project.defs.poc.constants import (
    KUBE_CONTEXT,
    NAMESPACE,
    SPARKAPP_MANIFEST,
)
from dagster_project.defs.poc.resources import SparkOperatorResource

GROUP_NAME = "poc"
_ROW_RE = re.compile(r"rows=(\d+)")


@dg.asset(group_name=GROUP_NAME, kinds={"spark", "iceberg", "bronze"})
def poc_spark_ingest(
    context: dg.AssetExecutionContext,
    spark_operator: SparkOperatorResource,
) -> dg.MaterializeResult:
    """SparkApplication을 제출해 Iceberg 샘플 테이블을 적재한다(호스트→kind)."""
    manifest = yaml.safe_load(Path(SPARKAPP_MANIFEST).read_text())
    name = manifest["metadata"]["name"]
    context.log.info(
        f"SparkApplication 제출: {name} (context={spark_operator.kube_context})"
    )

    state, logs = spark_operator.submit_and_wait(manifest)
    context.log.info(logs)

    if state != "COMPLETED":
        raise dg.Failure(description=f"SparkApplication 실패: {name} state={state}")

    match = _ROW_RE.search(logs)
    rows = int(match.group(1)) if match else None
    return dg.MaterializeResult(
        metadata={
            "state": state,
            "rows": rows if rows is not None else "unknown",
            "table": "jdbccat.poc.sample",
            "driver_pod": f"{name}-driver",
        }
    )


@dg.definitions
def poc_resources() -> dg.Definitions:
    """PoC 전용 리소스(Spark Operator 트리거)를 등록한다(load_defs가 수집)."""
    return dg.Definitions(
        resources={
            "spark_operator": SparkOperatorResource(
                kube_context=KUBE_CONTEXT, namespace=NAMESPACE
            ),
        }
    )
