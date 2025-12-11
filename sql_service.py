"""
SQL 기반 검색 서비스
LLM을 활용하여 자연어를 SQL 쿼리로 변환하고 실행

사용법:
1. _get_schema_info() 메서드에서 자신의 DB 스키마 정의
2. get_sql_service(db_path="your_data.db")로 서비스 초기화
"""

import sqlite3
import json
import requests
import logging
from typing import Dict, List, Optional, Tuple, Any
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SQLService:
    """SQL 기반 검색 및 통계 서비스"""

    def __init__(self, db_path: str = "your_data.db"):
        self.db_path = db_path
        self.vllm_url = config.VLLM_API_URL
        self.model_id = config.MODEL_ID

        # DB 스키마 정보
        self.schema_info = self._get_schema_info()

    def _get_schema_info(self) -> str:
        """
        데이터베이스 스키마 정보 정의

        ⚠️ 이 메서드를 수정하여 자신의 DB 스키마에 맞게 변경하세요.

        Returns:
            스키마 설명 문자열
        """
        return """
테이블: your_table (데이터 테이블)

주요 컬럼:
- id: INTEGER (기본키)
- date: TEXT (날짜 형식: YYYY-MM-DD HH:MM)
- year: INTEGER (연도)
- month: INTEGER (월)
- day: INTEGER (일)
- category: TEXT (카테고리/분류)
- sub_category: TEXT (하위 카테고리)
- region: TEXT (지역)
- name: TEXT (이름/명칭)
- value: INTEGER (값/수량)
- keywords: TEXT (키워드 JSON 배열 문자열)

참고:
- 이 스키마를 자신의 DB에 맞게 수정하세요
- _get_schema_info() 메서드에서 테이블 구조와 컬럼 설명을 정의합니다
"""

    def generate_sql_with_llm(self, user_query: str, entities: Dict[str, Any] = None) -> Tuple[str, str]:
        """
        LLM이 직접 SQL 쿼리를 생성

        Args:
            user_query: 사용자 질문
            entities: query_classifier에서 추출한 엔티티 (선택)

        Returns:
            (SQL 쿼리, 총 개수 조회 SQL 또는 None)
        """
        entity_hint = ""
        if entities:
            filtered = {k: v for k, v in entities.items() if v is not None}
            if filtered:
                entity_hint = f"\n질문에 명시된 엔티티:\n{json.dumps(filtered, ensure_ascii=False, indent=2)}\n"

        prompt = f"""당신은 SQL 전문가입니다. 사용자 질문을 분석하여 SQL 쿼리를 생성하세요.

사용자 질문: "{user_query}"{entity_hint}

{self.schema_info}

다음 JSON 형식으로 응답하세요:
{{
    "main_sql": "메인 SQL 쿼리 (SELECT ... FROM your_table ...)",
    "total_count_sql": "총 개수 조회 SQL (그룹핑인 경우만, 없으면 null)",
    "query_type": "aggregation|count|lookup"
}}

**SQL 작성 규칙**:
1. **LIMIT 자동 결정**:
   - "상위 N개", "top N" → LIMIT N
   - "전체", "모든", "다" → LIMIT 없음
   - 통계 질문 기본 → LIMIT 20

2. **GROUP BY 결정**:
   - 통계/집계 질문 → 적절한 컬럼으로 GROUP BY
   - 단순 건수 질문 → COUNT(*)

3. **query_type 결정**:
   - aggregation: 통계/집계 (GROUP BY 사용)
   - count: 단순 건수 (COUNT만)
   - lookup: 상세 조회 (개별 레코드)

**중요**: 오직 JSON만 출력. SQL은 반드시 문자열로 작성."""

        try:
            response = requests.post(
                self.vllm_url,
                json={
                    "model": self.model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.1
                },
                timeout=15
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # JSON 파싱
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)

            main_sql = data.get("main_sql", "")
            total_count_sql = data.get("total_count_sql")
            query_type = data.get("query_type", "aggregation")

            # SQL validation
            self._validate_sql(main_sql)
            if total_count_sql:
                self._validate_sql(total_count_sql)

            logger.info(f"LLM 생성 SQL: {main_sql}")
            return main_sql, total_count_sql, query_type

        except Exception as e:
            logger.error(f"LLM SQL 생성 실패: {e}")
            raise

    def _validate_sql(self, sql: str):
        """SQL 인젝션 방지를 위한 validation"""
        sql_upper = sql.upper()

        # 위험한 키워드 체크
        dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE", "--", ";"]
        for keyword in dangerous:
            if keyword in sql_upper:
                raise ValueError(f"위험한 SQL 키워드 감지: {keyword}")

        # SELECT로 시작하는지 확인
        if not sql_upper.strip().startswith("SELECT"):
            raise ValueError("SELECT 쿼리만 허용됩니다")

    def execute_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """SQL 쿼리 실행"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()
            logger.info(f"SQL 실행 완료: {len(results)}건")
            return results
        except Exception as e:
            logger.error(f"SQL 실행 실패: {e}")
            raise

    def generate_sql_query(self, user_query: str, entities: Dict[str, Any] = None, question_type: str = None) -> Tuple[str, str, str]:
        """자연어 질문을 SQL 쿼리로 변환"""
        sql_query, total_count_sql, query_type = self.generate_sql_with_llm(user_query, entities)
        return sql_query, query_type, total_count_sql

    def search(self, user_query: str, entities: Dict[str, Any] = None, question_type: str = None) -> Tuple[List[Dict[str, Any]], str, str, int]:
        """
        자연어 질문으로 SQL 검색 수행

        Args:
            user_query: 사용자 질문
            entities: query_classifier에서 추출한 엔티티 (선택)
            question_type: 질문 타입 (선택)

        Returns:
            (검색 결과, SQL 쿼리, 쿼리 타입, 총 개수)
        """
        sql_query, query_type, total_count_sql = self.generate_sql_query(user_query, entities, question_type)
        results = self.execute_query(sql_query)

        total_count = None
        if total_count_sql:
            total_result = self.execute_query(total_count_sql)
            if total_result:
                total_count = total_result[0].get('total', None)

        return results, sql_query, query_type, total_count

    def format_results_for_llm(self, results: List[Dict[str, Any]], query_type: str, total_count: int = None) -> str:
        """SQL 결과를 LLM이 이해하기 쉬운 형식으로 변환"""
        if not results:
            return "검색 결과가 없습니다."

        if total_count is None:
            total_count = len(results)

        context_parts = ["=== SQL 검색 결과 ===\n"]

        if query_type == "aggregation":
            if total_count and total_count > len(results):
                context_parts.append(f"집계 결과 (총 {total_count}건 중 상위 {len(results)}건):\n")
            else:
                context_parts.append(f"집계 결과 (총 {len(results)}건):\n")

            for idx, row in enumerate(results, 1):
                parts = []
                for key, value in row.items():
                    if value is not None and key not in ['text', 'keywords', 'id']:
                        parts.append(f"{key}: {value}")
                context_parts.append(f"[{idx}] " + ", ".join(parts))

        elif query_type == "count":
            context_parts.append(f"총 건수: {results[0].get('total', results[0].get('count', len(results)))}")

        else:  # lookup
            context_parts.append(f"조회 결과 (총 {len(results)}건):\n")
            for idx, row in enumerate(results, 1):
                parts = []
                for key, value in row.items():
                    if value is not None and key not in ['id']:
                        if isinstance(value, str) and len(value) > 150:
                            value = value[:150] + "..."
                        parts.append(f"{key}: {value}")
                context_parts.append(f"[{idx}] " + ", ".join(parts))

        return "\n".join(context_parts)


# ==================== 싱글톤 인스턴스 ====================

_sql_service: Optional[SQLService] = None


def get_sql_service(db_path: str = "your_data.db") -> SQLService:
    """싱글톤 SQL 서비스 인스턴스 반환"""
    global _sql_service
    if _sql_service is None:
        _sql_service = SQLService(db_path=db_path)
    return _sql_service
