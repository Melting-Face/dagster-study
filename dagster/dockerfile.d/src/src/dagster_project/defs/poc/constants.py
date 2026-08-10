"""PoC 자산 상수 — Spark Operator CRD 좌표·매니페스트 경로.

값은 환경변수로 override 가능(호스트 실행 유연성). 매니페스트 기본 경로는
레포 루트 기준으로 계산한다(이 모듈 위치에서 7단계 상위).
"""

import os
from pathlib import Path

# Kubeflow Spark Operator CRD 좌표
CRD_GROUP = "sparkoperator.k8s.io"
CRD_VERSION = "v1beta2"
CRD_PLURAL = "sparkapplications"

# 호스트 → kind 접속 컨텍스트·네임스페이스
KUBE_CONTEXT = os.environ.get("POC_KUBE_CONTEXT", "kind-lakehouse")
NAMESPACE = os.environ.get("POC_NAMESPACE", "default")

# 커밋된 SparkApplication 매니페스트(단일 출처). 환경변수로 override 가능.
_DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[7] / "k8s" / "spark" / "sparkapplication-poc.yaml"
)
SPARKAPP_MANIFEST = os.environ.get("POC_SPARKAPP_MANIFEST", str(_DEFAULT_MANIFEST))
