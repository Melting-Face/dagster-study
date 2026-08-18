"""PoC: Spark → Iceberg(JDBC 카탈로그, SeaweedFS S3) write/read.

성공 게이트 검증용 최소 잡. 카탈로그·S3 접속 정보는 환경변수로 주입받는다
(크리덴셜 비노출 — SparkApplication이 Secret에서 env로 전달).
Phase 2에서 이 자리를 실제 대용량 CSV.gz 적재로 대체한다.
"""

import os

from pyspark.sql import SparkSession

# 카탈로그 이름은 **모든 엔진이 같아야 한다**. Iceberg JDBC 카탈로그는 catalog_name으로
# 네임스페이스·테이블 레지스트리를 분할하므로, 이름이 다르면 같은 DB를 봐도
# 서로의 테이블이 보이지 않는다
# (2026-08-18 실측: Spark=jdbccat vs Dagster=iceberg로 갈려 있었다).
# 정본은 `iceberg` — Trino iceberg.properties·Dagster common/constants.py와 일치시킨다.
CATALOG = os.environ.get("ICEBERG_CATALOG_NAME", "iceberg")
NAMESPACE = "poc"
TABLE = f"{CATALOG}.{NAMESPACE}.sample"


def build_spark() -> SparkSession:
    """Iceberg JDBC 카탈로그 + S3FileIO(SeaweedFS, path-style) 세션을 만든다."""
    prefix = f"spark.sql.catalog.{CATALOG}"
    return (
        SparkSession.builder.appName("poc-ingest")
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(prefix, "org.apache.iceberg.spark.SparkCatalog")
        .config(f"{prefix}.catalog-impl", "org.apache.iceberg.jdbc.JdbcCatalog")
        .config(f"{prefix}.uri", os.environ["ICEBERG_JDBC_URI"])
        .config(f"{prefix}.jdbc.user", os.environ["PG_USER"])
        .config(f"{prefix}.jdbc.password", os.environ["PG_PASSWORD"])
        .config(f"{prefix}.warehouse", os.environ["ICEBERG_WAREHOUSE"])
        .config(f"{prefix}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config(f"{prefix}.s3.endpoint", os.environ["S3_ENDPOINT"])
        .config(f"{prefix}.s3.path-style-access", "true")
        .config(f"{prefix}.s3.access-key-id", os.environ["S3_ACCESS_KEY"])
        .config(f"{prefix}.s3.secret-access-key", os.environ["S3_SECRET_KEY"])
        .getOrCreate()
    )


def main() -> None:
    """샘플 테이블을 Iceberg에 write하고 read-back으로 검증한다."""
    spark = build_spark()

    # 네임스페이스 + 샘플 테이블 write(createOrReplace로 멱등)
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{NAMESPACE}")
    rows = [(1, "alice"), (2, "bob"), (3, "carol")]
    df = spark.createDataFrame(rows, "id int, name string")
    df.writeTo(TABLE).createOrReplace()

    # read-back 검증 (TABLE은 상수라 인젝션 아님)
    count = spark.sql(f"SELECT count(*) AS c FROM {TABLE}").collect()[0]["c"]  # noqa: S608
    print(f"[poc] wrote table={TABLE} rows={count}", flush=True)
    spark.sql(f"SELECT * FROM {TABLE} ORDER BY id").show(truncate=False)  # noqa: S608

    spark.stop()


if __name__ == "__main__":
    main()
