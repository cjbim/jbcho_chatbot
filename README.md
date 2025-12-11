# SQL 기반 데이터 분석 챗봇

FastAPI 백엔드와 SQL 기반의 자연어 데이터 분석 챗봇입니다.

SQLite 데이터베이스와 LLM을 활용하여 자연어 질문을 SQL로 변환하고,
검색된 데이터를 바탕으로 통계, 차트, 상세 내역을 제공합니다.

## 특징

- **자연어 → SQL 변환**: 복잡한 SQL 없이 자연어로 데이터 조회
- **실시간 스트리밍**: Server-Sent Events 기반 실시간 응답
- **차트 시각화**: Chart.js를 활용한 파이/막대 차트 자동 생성
- **유연한 스키마**: 다양한 도메인에 적용 가능

## 프로젝트 구조

```
├── app.py                  # FastAPI 백엔드 서버
├── sql_service.py          # SQL 서비스 (자연어 → SQL 변환)
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

## 주요 기능

### 1. 자연어 질문 처리
```
"서울 지역 2025년 8월 장애 통계"
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
- 파이 차트: 비율/분포 표시
- 막대 차트: 순위/비교 표시
- 스트리밍 완료 후 자동 렌더링

## 설치 및 실행

### 사전 준비

1. **vLLM 서버** (localhost:8000)
   - LLM 모델 로드 필요

2. **SQLite 데이터베이스**
   - 프로젝트 루트에 `.db` 파일 준비

### 설치

```bash
pip install -r requirements.txt
```

### 설정

`config.py` 수정:
```python
VLLM_API_URL = "http://localhost:8000/v1/chat/completions"
MODEL_ID = "/model"
HOST = "0.0.0.0"
PORT = 7860
```

### 실행

```bash
python app.py
```

브라우저에서 `http://localhost:7860` 접속

## 커스터마이징

### 데이터베이스 스키마 변경

`sql_service.py`의 `_get_schema_info()` 메서드에서 스키마 정의:

```python
def _get_schema_info(self) -> str:
    return """
테이블: your_table

주요 컬럼:
- id: INTEGER (기본키)
- date: TEXT (날짜)
- category: TEXT (분류)
- region: TEXT (지역)
- value: INTEGER (값)
...
"""
```

### SQL 생성 규칙 수정

`sql_service.py`의 `generate_sql_with_llm()` 메서드에서 프롬프트 수정:

```python
**SQL 작성 규칙**:
1. LIMIT 자동 결정
2. GROUP BY 자동 결정
3. WHERE 조건 처리
...
```

### 프론트엔드 커스터마이징

- `static/index.html`: 레이아웃 변경
- `static/style.css`: 스타일 변경
- `static/script.js`: 차트/스트리밍 로직

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

## 문제 해결

### vLLM 연결 오류
```bash
curl http://localhost:8000/v1/models
```

### 토큰 초과
질문을 더 구체적으로 (지역, 기간, 조건 지정)

### 차트 미표시
브라우저 새로고침 후 재시도

## API 문서

- Swagger UI: `http://localhost:7860/docs`
- ReDoc: `http://localhost:7860/redoc`

## 라이선스

MIT
