"""
3-Layer LLM 기반 질문 분류 모듈
데이터 관련 질문인지 LLM으로 판단하고 RAG를 트리거합니다.

Architecture:
- Layer 1: Query Analysis (쿼리 분석 - 의도, 엔티티, 키워드 추출)
- Layer 2: Relevance Decision (관련성 판단 - RAG 필요 여부 결정)
- Layer 3: RAG Trigger (RAG 실행 - 검색 파라미터 생성)
"""

import json
import requests
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Data Classes ====================

@dataclass
class QueryAnalysis:
    """Layer 1 출력: 쿼리 분석 결과"""
    intent: str  # 질문 의도 (예: "통계조회", "데이터검색", "일반대화")
    entities: Dict[str, Any]  # 추출된 엔티티
    keywords: list  # 핵심 키워드
    question_type: str  # 질문 유형 (aggregation, lookup, general)
    confidence: float  # 분석 신뢰도 (0.0 ~ 1.0)


@dataclass
class RelevanceDecision:
    """Layer 2 출력: 관련성 판단 결과"""
    is_retail_related: bool  # 도메인 데이터 관련 여부
    requires_rag: bool  # RAG 필요 여부
    confidence: float  # 판단 신뢰도 (0.0 ~ 1.0)
    reason: str  # 판단 이유


@dataclass
class RAGConfig:
    """Layer 3 출력: RAG 검색 설정"""
    use_rag: bool  # RAG 사용 여부
    search_method: str  # 검색 방법: "sql"
    top_k: int  # 검색할 결과 수
    score_threshold: float  # 최소 유사도 점수
    search_query: str  # 최적화된 검색 쿼리
    metadata_filter: Optional[Dict] = None  # 메타데이터 필터


# ==================== Layer 1: Query Analysis ====================

class QueryAnalyzer:
    """쿼리 분석 레이어 - LLM으로 질문의 의도와 엔티티 추출"""

    def __init__(self, vllm_url: str = None, model_id: str = None):
        self.vllm_url = vllm_url or config.VLLM_API_URL
        self.model_id = model_id or config.MODEL_ID

    def analyze(self, query: str) -> QueryAnalysis:
        """
        질문을 분석하여 의도, 엔티티, 키워드 추출

        Args:
            query: 사용자 질문

        Returns:
            QueryAnalysis 객체
        """
        prompt = f"""당신은 질문 분석 전문가입니다. 아래 사용자 질문을 분석하세요.

사용자 질문: "{query}"

다음 정보를 JSON 형식으로 추출하세요:
{{
    "intent": "질문의 주요 의도 (예: 데이터통계, 항목조회, 일반대화, 기술질문 등)",
    "entities": {{
        "category": "카테고리명 (없으면 null)",
        "item_type": "항목 유형 (없으면 null)",
        "region": "지역명 (없으면 null)",
        "year": 연도 숫자 (예: 2025, 없으면 null),
        "month": 월 숫자 (예: 7, 없으면 null)
    }},
    "keywords": ["핵심", "키워드", "리스트"],
    "question_type": "aggregation (통계/집계) | lookup (조회/검색) | general (일반대화)",
    "confidence": 0.0에서 1.0 사이의 분석 신뢰도
}}

**중요**: 오직 JSON만 출력하세요. 다른 설명은 불필요합니다."""

        try:
            response = requests.post(
                self.vllm_url,
                json={
                    "model": self.model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.1
                },
                timeout=10
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

            return QueryAnalysis(
                intent=data.get("intent", "unknown"),
                entities=data.get("entities", {}),
                keywords=data.get("keywords", []),
                question_type=data.get("question_type", "general"),
                confidence=float(data.get("confidence", 0.5))
            )

        except requests.exceptions.Timeout:
            logger.warning("Layer 1 타임아웃 - 기본값 반환")
            return self._fallback_analysis(query)
        except Exception as e:
            logger.error(f"Layer 1 분석 실패: {e}")
            return self._fallback_analysis(query)

    def _fallback_analysis(self, query: str) -> QueryAnalysis:
        """LLM 실패 시 간단한 키워드 매칭으로 대체"""
        data_keywords = ["통계", "데이터", "조회", "검색", "목록", "내역"]
        keywords = [kw for kw in data_keywords if kw in query]

        return QueryAnalysis(
            intent="unknown",
            entities={},
            keywords=keywords,
            question_type="general",
            confidence=0.3
        )


# ==================== Layer 2: Relevance Decision ====================

class RelevanceDecider:
    """관련성 판단 레이어 - Layer 1 결과를 바탕으로 RAG 필요 여부 결정"""

    def __init__(self, vllm_url: str = None, model_id: str = None):
        self.vllm_url = vllm_url or config.VLLM_API_URL
        self.model_id = model_id or config.MODEL_ID

    def decide(self, query: str, analysis: QueryAnalysis) -> RelevanceDecision:
        """
        Layer 1 결과를 바탕으로 RAG 필요 여부 판단

        Args:
            query: 원본 질문
            analysis: Layer 1 분석 결과

        Returns:
            RelevanceDecision 객체
        """
        prompt = f"""당신은 질문 분류 전문가입니다. 주어진 질문이 "도메인 데이터"와 관련이 있는지 판단하세요.

**도메인 데이터란?**
- 데이터베이스에 저장된 비즈니스 데이터
- 통계, 집계, 조회가 필요한 데이터

**사용자 질문:**
"{query}"

**질문 분석 결과 (Layer 1):**
- 의도: {analysis.intent}
- 엔티티: {json.dumps(analysis.entities, ensure_ascii=False)}
- 키워드: {analysis.keywords}
- 질문 유형: {analysis.question_type}

아래 JSON 형식으로 판단하세요:
{{
    "is_retail_related": true 또는 false,
    "requires_rag": true 또는 false (도메인 관련이고 데이터 검색이 필요하면 true),
    "confidence": 0.0에서 1.0 사이의 신뢰도,
    "reason": "판단 이유를 한 문장으로"
}}

**판단 기준:**
1. 데이터 조회/통계가 필요한 질문이면 RAG 필요
2. 일반 인사말, 날씨, 계산, 일반 대화 등은 도메인 무관

**중요**: 오직 JSON만 출력하세요."""

        try:
            response = requests.post(
                self.vllm_url,
                json={
                    "model": self.model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.1
                },
                timeout=10
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

            return RelevanceDecision(
                is_retail_related=data.get("is_retail_related", False),
                requires_rag=data.get("requires_rag", False),
                confidence=float(data.get("confidence", 0.5)),
                reason=data.get("reason", "")
            )

        except Exception as e:
            logger.error(f"Layer 2 판단 실패: {e}")
            return self._fallback_decision(analysis)

    def _fallback_decision(self, analysis: QueryAnalysis) -> RelevanceDecision:
        """LLM 실패 시 Layer 1 결과로 간단 판단"""
        related = (
            analysis.question_type in ["aggregation", "lookup"] and
            len(analysis.keywords) > 0
        )

        return RelevanceDecision(
            is_retail_related=related,
            requires_rag=related,
            confidence=0.5,
            reason="Fallback decision based on keywords"
        )


# ==================== Layer 3: RAG Trigger ====================

class RAGTrigger:
    """RAG 실행 레이어 - Layer 2 결과를 바탕으로 RAG 검색 파라미터 생성"""

    def __init__(self):
        pass

    def generate_config(
        self,
        query: str,
        analysis: QueryAnalysis,
        decision: RelevanceDecision
    ) -> RAGConfig:
        """
        RAG 검색 설정 생성

        Args:
            query: 원본 질문
            analysis: Layer 1 분석 결과
            decision: Layer 2 판단 결과

        Returns:
            RAGConfig 객체
        """
        if not decision.requires_rag:
            return RAGConfig(
                use_rag=False,
                search_method="none",
                top_k=0,
                score_threshold=0.0,
                search_query=""
            )

        # 질문 유형에 따라 검색 방법과 파라미터 결정
        if analysis.question_type == "aggregation":
            search_method = "sql"
            top_k = config.DEFAULT_TOP_K
            score_threshold = 0.5
        elif analysis.question_type == "lookup":
            search_method = "sql"
            top_k = 50
            score_threshold = 0.7
        else:
            search_method = "sql"
            top_k = config.DEFAULT_TOP_K
            score_threshold = 0.7

        # 검색 쿼리 최적화
        search_query = self._optimize_search_query(query, analysis)

        return RAGConfig(
            use_rag=True,
            search_method=search_method,
            top_k=top_k,
            score_threshold=score_threshold,
            search_query=search_query,
            metadata_filter=None
        )

    def _optimize_search_query(self, query: str, analysis: QueryAnalysis) -> str:
        """검색 쿼리 최적화"""
        search_parts = []

        entities = analysis.entities
        for key, value in entities.items():
            if value:
                search_parts.append(str(value))

        if search_parts:
            return " ".join(search_parts) + " " + query
        return query


# ==================== Main Classifier ====================

class LLMQueryClassifier:
    """3-Layer LLM 기반 질문 분류기"""

    def __init__(self):
        self.analyzer = QueryAnalyzer()
        self.decider = RelevanceDecider()
        self.trigger = RAGTrigger()

    def classify(self, query: str) -> Tuple[bool, RAGConfig, Dict[str, Any]]:
        """
        질문을 3-layer로 분석하여 RAG 사용 여부 결정

        Args:
            query: 사용자 질문

        Returns:
            (RAG 사용 여부, RAG 설정, 디버그 정보)
        """
        # Layer 1: Query Analysis
        logger.info(f"[Layer 1] 질문 분석 중: '{query[:50]}...'")
        analysis = self.analyzer.analyze(query)

        # Layer 2: Relevance Decision
        logger.info(f"[Layer 2] 관련성 판단 중...")
        decision = self.decider.decide(query, analysis)

        # Layer 3: RAG Trigger
        logger.info(f"[Layer 3] RAG 설정 생성 중...")
        rag_config = self.trigger.generate_config(query, analysis, decision)

        # 디버그 정보
        debug_info = {
            "layer1_analysis": {
                "intent": analysis.intent,
                "entities": analysis.entities,
                "keywords": analysis.keywords,
                "question_type": analysis.question_type,
                "confidence": analysis.confidence
            },
            "layer2_decision": {
                "is_retail_related": decision.is_retail_related,
                "requires_rag": decision.requires_rag,
                "confidence": decision.confidence,
                "reason": decision.reason
            },
            "layer3_config": {
                "use_rag": rag_config.use_rag,
                "top_k": rag_config.top_k,
                "score_threshold": rag_config.score_threshold,
                "search_query": rag_config.search_query
            }
        }

        return rag_config.use_rag, rag_config, debug_info


# ==================== 전역 인스턴스 ====================

_classifier: Optional[LLMQueryClassifier] = None


def get_classifier() -> LLMQueryClassifier:
    """싱글톤 분류기 인스턴스 반환"""
    global _classifier
    if _classifier is None:
        _classifier = LLMQueryClassifier()
    return _classifier


# ==================== 기존 API 호환성 유지 ====================

def should_use_rag(query: str, threshold: float = 0.3) -> bool:
    """RAG 사용 여부 판단 (기존 API 호환)"""
    classifier = get_classifier()
    use_rag, _, _ = classifier.classify(query)
    return use_rag


def is_retail_related(query: str) -> Tuple[bool, float]:
    """도메인 관련 여부 판단 (기존 API 호환)"""
    classifier = get_classifier()
    _, _, debug_info = classifier.classify(query)
    is_related = debug_info["layer2_decision"]["is_retail_related"]
    confidence = debug_info["layer2_decision"]["confidence"]
    return is_related, confidence
