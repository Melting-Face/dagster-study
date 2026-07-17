"""Trino 쿼리 엔진 공유 접속 리소스 (데이터셋 무관 공통).

Iceberg 유지보수 프로시저(`remove_orphan_files` 등)를 Trino에서 실행하기 위한
경량 접속 리소스. 접속 파라미터는 내부망 값(비밀 아님)이라 common.constants에서
기본값을 참조하고, 필요 시 환경변수로 재정의한다. 연결은 자산/op가 아닌
리소스에 두는 프로젝트 컨벤션을 따른다.
"""

from trino.dbapi import connect

import dagster as dg


class TrinoResource(dg.ConfigurableResource):
    """Trino 접속 리소스 — SQL·유지보수 프로시저 실행용."""

    host: str
    port: int
    user: str
    catalog: str

    def execute(self, statement: str) -> list:
        """단일 SQL/프로시저를 실행하고 결과 행을 반환한다(DDL/프로시저는 빈 리스트)."""
        conn = connect(
            host=self.host,
            port=self.port,
            user=self.user,
            catalog=self.catalog,
            # 내부망 평문(외부 노출 시 https 필요 — docs/security.md §4-2)
            http_scheme="http",
        )
        try:
            cursor = conn.cursor()
            cursor.execute(statement)
            return cursor.fetchall()
        finally:
            conn.close()
