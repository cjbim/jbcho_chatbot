from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
from typing import List, Dict, Optional
import asyncio
import httpx
from sql_service import get_sql_service
from query_classifier import get_classifier
import config

app = FastAPI(title="SQL Data Analysis Chatbot API")

# 진행 중인 요청 추적 (중단 기능용)
active_requests: Dict[str, bool] = {}

# 동시 LLM 요청 제한 (vLLM 과부하 방지)
llm_semaphore = asyncio.Semaphore(64)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQL 서비스 초기화
try:
    sql_service = get_sql_service()
    print("✓ SQL 서비스 초기화 완료")
except Exception as e:
    print(f"✗ SQL 서비스 초기화 실패: {e}")
    sql_service = None

# 요청 모델
class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 4096
    use_rag: Optional[bool] = None
    top_k: int = config.DEFAULT_TOP_K
    request_id: Optional[str] = None

# 응답 모델
class ChatResponse(BaseModel):
    message: str
    success: bool

# 중단 요청 모델
class StopRequest(BaseModel):
    request_id: str

def get_system_prompt(rag_context: str) -> str:
    """시스템 프롬프트 생성"""
    if rag_context:
        return f"""당신은 SQL 데이터 분석 전문가입니다.

=== 검색된 데이터 ===
{rag_context}

답변 작성 규칙:
1. **데이터 완전성**: 검색된 모든 데이터를 빠짐없이 표시
2. **총 개수 표현**: "[조건]에 해당하는 N개 항목"으로 표현
3. 통계 질문: **표 형식**으로 정리 (마크다운 테이블)
4. **차트 시각화** (명시적 요청 시에만):
   - "차트", "그래프", "파이차트", "막대그래프" 등 요청 시에만 생성
   - 단순 "통계", "보여줘"는 표만 제공
   - **Chart.js JSON 형식**:

   파이 차트:
   ```chartjs
   {{
     "type": "pie",
     "title": "제목",
     "labels": ["항목1", "항목2"],
     "data": [값1, 값2]
   }}
   ```

   막대 그래프:
   ```chartjs
   {{
     "type": "bar",
     "title": "제목",
     "labels": ["항목1", "항목2"],
     "data": [값1, 값2]
   }}
   ```
5. 숫자는 정확하게, 간결하고 명확하게"""
    else:
        return """당신은 친절하고 전문적인 AI 어시스턴트입니다.
사용자의 질문에 정확하고 도움이 되는 답변을 제공하세요."""

async def process_query(user_query: str, use_rag: Optional[bool], top_k: int):
    """질문 처리 및 RAG 컨텍스트 생성"""
    import time

    rag_context = ""
    debug_info = {}

    # RAG 사용 여부 자동 판단
    if use_rag is None:
        classifier = get_classifier()
        use_rag_decision, rag_config, debug_info = classifier.classify(user_query) if user_query else (False, None, {})
    else:
        use_rag_decision = use_rag
        rag_config = None

    if use_rag_decision and user_query and sql_service:
        try:
            if rag_config:
                search_query = rag_config.search_query
                search_method = rag_config.search_method
            else:
                search_query = user_query
                search_method = "sql"

            if search_method in ["sql", "both"]:
                entities = debug_info.get('layer1_analysis', {}).get('entities') if debug_info else None
                question_type = debug_info.get('layer1_analysis', {}).get('question_type') if debug_info else None

                sql_results, sql_query, query_type, total_stores = sql_service.search(search_query, entities, question_type)
                rag_context = sql_service.format_results_for_llm(sql_results, query_type, total_stores)

        except Exception as e:
            print(f"SQL 검색 오류: {e}")

    return rag_context, use_rag_decision

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """메인 페이지 반환"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """일반 채팅 API (스트리밍 없음)"""
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    user_query = request.messages[-1].get("content", "") if request.messages else ""
    rag_context, _ = await process_query(user_query, request.use_rag, request.top_k)

    system_prompt = get_system_prompt(rag_context)
    messages = [{"role": "system", "content": system_prompt}, *request.messages]

    try:
        timeout_config = httpx.Timeout(10.0, read=300.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(
                config.VLLM_API_URL,
                json={
                    "model": config.MODEL_ID,
                    "messages": messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature
                }
            )
            response.raise_for_status()
            result = response.json()
            assistant_message = result["choices"][0]["message"]["content"]
            return ChatResponse(message=assistant_message, success=True)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """스트리밍 채팅 API"""
    import time
    start_time = time.time()

    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    user_query = request.messages[-1].get("content", "") if request.messages else ""
    rag_context, _ = await process_query(user_query, request.use_rag, request.top_k)

    system_prompt = get_system_prompt(rag_context)
    messages = [{"role": "system", "content": system_prompt}, *request.messages]

    req_id = request.request_id or f"req_{asyncio.get_event_loop().time()}"
    active_requests[req_id] = True

    async def generate():
        async with llm_semaphore:
            try:
                timeout_config = httpx.Timeout(30.0, read=300.0, write=30.0)
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    async with client.stream(
                        "POST",
                        config.VLLM_API_URL,
                        json={
                            "model": config.MODEL_ID,
                            "messages": messages,
                            "max_tokens": request.max_tokens,
                            "temperature": request.temperature,
                            "stream": True,
                        }
                    ) as response:
                        response.raise_for_status()
                        buffer = b""
                        async for chunk in response.aiter_bytes(chunk_size=1024):
                            if not active_requests.get(req_id, True):
                                yield f"data: {json.dumps({'content': '', 'stopped': True})}\n\n"
                                break

                            buffer += chunk
                            lines = buffer.split(b'\n')
                            buffer = lines[-1]

                            for line_bytes in lines[:-1]:
                                try:
                                    line = line_bytes.decode('utf-8').strip()
                                    if not line or not line.startswith('data: '):
                                        continue

                                    data_str = line[6:]
                                    if data_str.strip() == '[DONE]':
                                        break

                                    data_json = json.loads(data_str)
                                    if 'choices' in data_json and len(data_json['choices']) > 0:
                                        choice = data_json['choices'][0]
                                        content = None
                                        if 'delta' in choice and 'content' in choice['delta']:
                                            content = choice['delta']['content']
                                        elif 'text' in choice:
                                            content = choice['text']

                                        if content:
                                            yield f"data: {json.dumps({'content': content})}\n\n"
                                except (json.JSONDecodeError, UnicodeDecodeError):
                                    continue
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                if req_id in active_requests:
                    del active_requests[req_id]

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/chat/stop")
async def stop_generation(stop_request: StopRequest):
    """LLM 응답 생성 중단 API"""
    request_id = stop_request.request_id
    if request_id in active_requests:
        active_requests[request_id] = False
        return {"success": True, "message": f"Request {request_id} stopped"}
    return {"success": False, "message": f"Request {request_id} not found"}

# Static 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
