#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["boto3"]
# ///
"""원천 csv.gz를 SeaweedFS(S3 호환) warehouse 버킷의 raw/로 업로드한다(파이프라인 입력).

왜 이 스크립트인가:
    SeaweedFS Admin UI(:23646)는 프론트엔드 JS에 500MB 업로드 상한이 하드코딩돼 있어
    대용량 원천(chartevents·labevents ≈ 3.3GB)을 UI로 올릴 수 없다.
    boto3 upload_file은 TransferConfig 기반 자동 멀티파트로 상한 없이 안정 적재한다.

대상 파일(매니페스트)은 Dagster 적재 자산이 실제로 읽는 파일과 1:1로 고정돼 있다.
    - eICU  : defs/eicu/assets.py       (SOURCE_BASE = s3://warehouse/raw/eicu)
    - MIMIC : defs/mimic_iv/assets.py   (SOURCE_BASE = s3://warehouse/raw/mimiciv)
    S3 키 = s3://warehouse/raw/<상대경로>. 목록에 없는 파일은 업로드하지 않는다.

전제:
    - 리포 루트 .env에 AWS_ACCESS_KEY_ID/SECRET/DEFAULT_REGION 존재
    - compose 스택 기동(SeaweedFS S3 엔드포인트가 호스트 localhost:8333에 게시됨)

실행(의존성은 위 PEP 723 블록에 선언 — uv가 자동 provisioning):
    uv run scripts/upload_raw_to_seaweedfs.py -n ./data/raw   # 미리보기
    uv run scripts/upload_raw_to_seaweedfs.py ./data/raw      # 업로드

로컬 파일 배치: 두 방식 모두 지원한다.
    (a) raw/ 구조 그대로:  <LOCAL_DIR>/mimiciv/icu/chartevents.csv.gz ...
    (b) 한 폴더에 평평하게: <LOCAL_DIR>/chartevents.csv.gz ...  (basename 자동 매칭)

스타일: 스크립트 컨벤션(docs/conventions/python.md)에 따라 절차형으로 쓴다.
    선언(상수)은 상단에 두고 진입은 하단(호이스팅), 클래스·보조 함수로 쪼개지 않고
    main에서 위→아래로 실행한다(캡슐화·함수화 최소화). 근거는 가독성/LoB.
"""

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 대상 매니페스트: raw/ 기준 상대경로 (= 자산이 읽는 파일)
EICU_FILES = [
    "eicu/patient.csv.gz",
    "eicu/diagnosis.csv.gz",
    "eicu/nurseCharting.csv.gz",
]
MIMICIV_FILES = [
    "mimiciv/icu/icustays.csv.gz",
    "mimiciv/icu/chartevents.csv.gz",
    "mimiciv/icu/inputevents.csv.gz",
    "mimiciv/icu/outputevents.csv.gz",
    "mimiciv/icu/d_items.csv.gz",
    "mimiciv/hosp/patients.csv.gz",
    "mimiciv/hosp/admissions.csv.gz",
    "mimiciv/hosp/labevents.csv.gz",
    "mimiciv/hosp/d_labitems.csv.gz",
    "mimiciv/hosp/prescriptions.csv.gz",
    "mimiciv/hosp/microbiologyevents.csv.gz",
]
DATASETS = {"eicu": EICU_FILES, "mimiciv": MIMICIV_FILES}


def main() -> int:
    """.env·인자를 읽어 대상 매니페스트를 SeaweedFS raw/로 업로드한다(절차형)."""
    # 1) 인자
    parser = argparse.ArgumentParser(
        description="로컬 원천 csv.gz를 SeaweedFS warehouse/raw/로 업로드",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "local_dir", nargs="?", default="./data/raw", help="원천 파일 로컬 디렉토리"
    )
    parser.add_argument(
        "-e",
        "--endpoint",
        default=os.environ.get("S3_ENDPOINT_URL", "http://localhost:8333"),
        help="S3 엔드포인트(호스트 기준)",
    )
    parser.add_argument(
        "-b", "--bucket", default=os.environ.get("S3_BUCKET", "warehouse")
    )
    parser.add_argument(
        "-d", "--dataset", choices=["all", "eicu", "mimiciv"], default="all"
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true", help="전송 없이 매칭만 출력"
    )
    args = parser.parse_args()

    # 2) boto3 (--help 이후 로드 → 도움말은 미설치여도 동작. uv run이 PEP 723으로 설치)
    try:
        import boto3
        from boto3.s3.transfer import TransferConfig
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError
    except ModuleNotFoundError:
        sys.exit("❌ boto3가 필요합니다: uv run scripts/upload_raw_to_seaweedfs.py ...")

    # 3) .env 로드 (KEY=VALUE; 인라인 주석·따옴표 제거; 기존 env 우선)
    env_path = REPO_ROOT / ".env"
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            env_key, _, env_val = line.partition("=")
            env_key = env_key.strip()
            env_val = env_val.split(" #", 1)[0].strip().strip("'\"")
            if env_key:
                os.environ.setdefault(env_key, env_val)

    for cred in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        if not os.environ.get(cred):
            sys.exit(f"❌ .env에 {cred}가 없습니다")

    local_dir = Path(args.local_dir)
    if not local_dir.is_dir():
        sys.exit(f"❌ 로컬 디렉토리가 없습니다: {local_dir}")

    if args.dataset == "all":
        manifest = EICU_FILES + MIMICIV_FILES
    else:
        manifest = DATASETS[args.dataset]

    print(f"▶ 엔드포인트 : {args.endpoint}")
    print(f"▶ 대상 버킷  : s3://{args.bucket}/raw   (dataset={args.dataset})")
    print(f"▶ 로컬 소스  : {local_dir}")
    if args.dry_run:
        print("▶ 모드       : DRY-RUN (실제 전송 안 함)")
    print()

    # 4) S3 클라이언트 (SeaweedFS는 가상호스트 미지원 → path-style 강제, iceberg와 동일)
    s3 = boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
    )
    try:
        s3.list_buckets()
    except (ClientError, BotoCoreError) as exc:
        sys.exit(f"❌ S3 엔드포인트 접속 실패: {args.endpoint}\n   ({exc})")

    # 버킷 없으면 생성 (멱등)
    try:
        s3.head_bucket(Bucket=args.bucket)
    except ClientError:
        print(f"• 버킷 생성: s3://{args.bucket}")
        if not args.dry_run:
            s3.create_bucket(Bucket=args.bucket)

    # 5) 매니페스트 순회 업로드 (8MB↑는 64MB 청크 멀티파트로 병렬 전송)
    transfer = TransferConfig(
        multipart_threshold=8 * 1024 * 1024,
        multipart_chunksize=64 * 1024 * 1024,
        max_concurrency=4,
    )
    found = uploaded = 0
    missing: list[str] = []
    for rel in manifest:
        direct = local_dir / rel
        if direct.is_file():
            src = direct
        else:
            src = next(iter(local_dir.rglob(Path(rel).name)), None)
        if src is None:
            print(f"  ✗ 없음   {rel}")
            missing.append(rel)
            continue
        found += 1
        size_mb = src.stat().st_size / 1024 / 1024
        size_str = f"{size_mb / 1024:.1f}GB" if size_mb >= 1024 else f"{size_mb:.1f}MB"
        key = f"raw/{rel}"
        target = f"s3://{args.bucket}/{key}"
        if args.dry_run:
            print(f"  → [{size_str}]  {src}  →  {target}")
            continue
        print(f"  ↑ [{size_str}]  {target}")
        s3.upload_file(str(src), args.bucket, key, Config=transfer)
        uploaded += 1

    # 6) 요약
    print()
    print(
        f"요약: 대상 {len(manifest)} / 로컬발견 {found} / "
        f"업로드 {uploaded} / 누락 {len(missing)}"
    )
    if missing:
        print(f"누락 파일(로컬에 없음): {', '.join(missing)}", file=sys.stderr)
    if not args.dry_run:
        print(
            f"확인: aws --endpoint-url {args.endpoint} "
            f"s3 ls s3://{args.bucket}/raw/ --recursive --human-readable"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
