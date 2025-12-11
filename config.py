"""
SQL 챗봇 설정 파일
필요에 따라 이 파일의 값을 수정하세요.
"""

# vLLM 설정
VLLM_API_URL = "http://localhost:8000/v1/chat/completions"
MODEL_ID = "/model"  # vLLM 실행 시 사용된 모델 ID

# RAG 검색 설정
DEFAULT_TOP_K = 30  # 기본 검색 결과 수

# 서버 설정
HOST = "0.0.0.0"
PORT = 7860
