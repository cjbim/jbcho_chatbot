# SQL 기반 데이터 분석 챗봇

FastAPI 백엔드와 SQL 기반의 자연어 데이터 분석 챗봇입니다.

SQLite 데이터베이스와 LLM을 활용하여 자연어 질문을 SQL로 변환하고,
검색된 데이터를 바탕으로 통계, 차트, 상세 내역을 제공합니다.

## 특징

- **자연어 → SQL 변환**: 복잡한 SQL 없이 자연어로 데이터 조회
- **실시간 스트리밍**: Server-Sent Events 기반 실시간 응답
- **차트 시각화**: Chart.js를 활용한 파이/막대 차트 자동 생성
- **유연한 스키마**: 다양한 도메인에 적용 가능

## 빠른 시작 (Quick Start)

### 1단계: 의존성 설치

```bash
pip install -r requirements.txt
```

### 2단계: vLLM 서버 실행

```bash
# vLLM 서버가 localhost:8000에서 실행 중이어야 합니다
vllm serve /path/to/model --port 8000
```

### 3단계: DB 스키마 정의

`sql_service.py` 파일의 `_get_schema_info()` 메서드를 수정하여 자신의 DB 스키마를 정의합니다:

```python
def _get_schema_info(self) -> str:
    return """
테이블: sales_records (판매 데이터)

주요 컬럼:
- id: INTEGER (기본키)
- date: TEXT (날짜, YYYY-MM-DD)
- product_name: TEXT (상품명)
- category: TEXT (카테고리: 식품, 음료, 생활용품 등)
- region: TEXT (지역: 서울, 부산, 대구 등)
- quantity: INTEGER (판매 수량)
- price: INTEGER (판매 금액)
- store_name: TEXT (매장명)

예시 질문:
- "서울 지역 식품 카테고리 판매 통계" → region='서울' AND category='식품'
- "월별 판매 추이" → GROUP BY month
- "상위 10개 매장" → ORDER BY SUM(price) DESC LIMIT 10
"""
```

### 4단계: DB 경로 설정

`sql_service.py` 하단의 `get_sql_service()` 함수에서 DB 경로 수정:

```python
def get_sql_service(db_path: str = "your_data.db") -> SQLService:
    # your_data.db를 실제 DB 파일명으로 변경
```

### 5단계: 서버 실행

```bash
python app.py
```

브라우저에서 `http://localhost:7860` 접속

## 프로젝트 구조

```
├── app.py                  # FastAPI 백엔드 서버
├── sql_service.py          # SQL 서비스 (자연어 → SQL 변환) ⭐ 스키마 정의
├── query_classifier.py     # 3-Layer 질문 분류기
├── config.py               # 설정 파일
├── your_data.db            # SQLite 데이터베이스
├── requirements.txt        # Python 의존성
├── static/                 # 프론트엔드 파일
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

## 커스터마이징 가이드

### 1. DB 스키마 정의 (필수)

`sql_service.py`의 `_get_schema_info()` 메서드에서 스키마를 상세히 정의할수록 LLM이 정확한 SQL을 생성합니다.

**좋은 스키마 정의 예시:**

```python
def _get_schema_info(self) -> str:
    return """
테이블: orders (주문 데이터, 총 50,000건)

주요 컬럼:
- order_id: INTEGER (기본키)
- order_date: TEXT (주문일, YYYY-MM-DD HH:MM)
- customer_name: TEXT (고객명)
- product_category: TEXT (상품 카테고리)
  * 가능한 값: 전자제품, 의류, 식품, 가구, 도서
- region: TEXT (배송 지역)
  * 가능한 값: 서울, 경기, 부산, 대구, 인천, 광주, 대전
- amount: INTEGER (주문 금액)
- status: TEXT (주문 상태: 완료, 취소, 배송중)

자주 사용되는 쿼리 패턴:
- 카테고리별 통계: GROUP BY product_category
- 지역별 통계: GROUP BY region
- 월별 추이: GROUP BY strftime('%Y-%m', order_date)
"""
```

### 2. SQL 생성 규칙 커스터마이징

`sql_service.py`의 `generate_sql_with_llm()` 메서드 내 프롬프트를 수정하여 도메인에 맞는 SQL 규칙을 추가할 수 있습니다:

```python
**SQL 작성 규칙**:
1. 날짜 필터: WHERE order_date LIKE '2025-01%'
2. 금액 합계: SUM(amount) as total_amount
3. 건수: COUNT(*) as count
...
```

### 3. 프론트엔드 커스터마이징

- `static/index.html`: 타이틀, 예시 버튼 변경
- `static/style.css`: 색상, 레이아웃 변경
- `static/script.js`: 차트 스타일, 추가 기능

## 주요 기능

### 1. 자연어 질문 처리
```
"서울 지역 2025년 1월 판매 통계"
→ SQL 자동 생성 및 실행
→ 결과를 표/차트로 시각화
```

### 2. 3-Layer 질문 분류
```
Layer 1: 의도 분석 (통계/조회/개수)
Layer 2: 도메인 관련성 판단
Layer 3: 검색 설정 (SQL 타입, 파라미터)
```

### 3. 다양한 쿼리 타입
- **통계 (aggregation)**: GROUP BY, COUNT 기반 집계
- **개수 (count)**: 단순 카운트 쿼리
- **조회 (lookup)**: 상세 데이터 조회

### 4. 차트 시각화
- 파이 차트: 비율/분포 표시 (예: "파이차트로 보여줘")
- 막대 차트: 순위/비교 표시 (예: "막대그래프로 보여줘")
- 스트리밍 완료 후 자동 렌더링

## API 엔드포인트

### GET `/`
메인 페이지

### POST `/api/chat/stream`
스트리밍 채팅 API

```json
{
  "messages": [
    {"role": "user", "content": "질문 내용"}
  ],
  "temperature": 0.7,
  "max_tokens": 4096
}
```

### POST `/api/chat/stop`
스트리밍 중단

## 질문 예시

### 통계
- "카테고리별 통계 파이차트로 보여줘"
- "지역별 발생 건수 상위 10개"
- "2025년 월별 추이"

### 개수
- "전체 몇 건이야?"
- "서울 지역 몇 개?"

### 조회
- "A항목 상세 내역"
- "최근 발생 목록"

## 시스템 흐름

```
사용자 질문
    ↓
[질문 분류] 3-Layer 분석
    ↓
[SQL 생성] LLM이 자연어 → SQL 변환
    ↓
[실행] SQLite 쿼리 실행
    ↓
[포맷팅] 결과 정리
    ↓
[응답 생성] LLM이 자연어 응답 + 차트 JSON
    ↓
[렌더링] 프론트엔드에서 마크다운 + 차트 표시
```

## 설정 파일 (config.py)

```python
# vLLM 설정
VLLM_API_URL = "http://localhost:8000/v1/chat/completions"
MODEL_ID = "/model"

# 검색 설정
DEFAULT_TOP_K = 30

# 서버 설정
HOST = "0.0.0.0"
PORT = 7860
```

## 문제 해결

### vLLM 연결 오류
```bash
curl http://localhost:8000/v1/models
```

### 토큰 초과
질문을 더 구체적으로 (지역, 기간, 조건 지정)

### 차트 미표시
브라우저 새로고침 후 재시도

### SQL 생성 오류
`sql_service.py`의 스키마 정의가 정확한지 확인

## API 문서

- Swagger UI: `http://localhost:7860/docs`
- ReDoc: `http://localhost:7860/redoc`

## 라이선스

MIT
