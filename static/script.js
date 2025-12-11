// 메시지 히스토리
let messageHistory = [];
let isLoading = false;
let currentRequestId = null;  // 현재 진행 중인 요청 ID
let currentReader = null;  // 현재 스트리밍 reader

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('messageInput');
    messageInput.focus();

    // textarea 자동 높이 조절
    messageInput.addEventListener('input', autoResize);

    // Mermaid 초기화
    if (typeof mermaid !== 'undefined') {
        mermaid.initialize({
            startOnLoad: false,
            theme: 'default',
            securityLevel: 'loose'
        });
    }

    // 시작 애니메이션
    showStartupAnimation();
});

function showStartupAnimation() {
    const logo = document.querySelector('.header-logo img');
    if (logo) {
        logo.style.opacity = '0';
        logo.style.transform = 'translateY(-20px)';
        setTimeout(() => {
            logo.style.transition = 'all 0.6s ease-out';
            logo.style.opacity = '1';
            logo.style.transform = 'translateY(0)';
        }, 100);
    }
}

function autoResize() {
    const textarea = document.getElementById('messageInput');
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

function handleKeyDown(event) {
    // Shift + Enter는 줄바꿈
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function sendExample(text) {
    const messageInput = document.getElementById('messageInput');
    messageInput.value = text;
    sendMessage();
}

async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();

    if (!message || isLoading) return;

    // 이전 요청이 진행 중이면 중단
    if (currentReader) {
        console.log('이전 요청 중단 중...');
        try {
            await currentReader.cancel();
        } catch (e) {
            console.log('Reader cancel 실패:', e);
        }
        currentReader = null;
    }

    // 웰컴 메시지 제거
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }

    // 입력 필드 초기화 및 높이 리셋
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // 사용자 메시지 표시
    addMessage(message, 'user');

    // 히스토리에 추가
    messageHistory.push({
        role: 'user',
        content: message
    });

    // 로딩 상태 표시
    isLoading = true;
    currentRequestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;  // 고유 요청 ID 생성
    toggleButton('stop');  // 버튼을 중단 모드로 변경
    const loadingElement = showLoading();

    try {
        // 미리 정의된 답변 체크
        const predefinedResponse = checkPredefinedResponse(message);
        if (predefinedResponse) {
            removeLoading(loadingElement);
            await simulateTypingResponse(predefinedResponse);
        } else {
            // API 호출 (스트리밍) - max_tokens 512로 제한
            await sendMessageStream(messageHistory, loadingElement);
        }
    } catch (error) {
        console.error('Error:', error);
        removeLoading(loadingElement);
        showError(error.message || '메시지 전송 중 오류가 발생했습니다.');
    } finally {
        isLoading = false;
        currentRequestId = null;
        currentReader = null;
        toggleButton('send');  // 버튼을 전송 모드로 복원
        messageInput.focus();
    }
}

function checkPredefinedResponse(message) {
    const lowerMessage = message.toLowerCase();

    // 제타큐브 관련 키워드
    if (lowerMessage.includes('제타큐브') || lowerMessage.includes('zetacube')) {
        return '제타큐브는 DePIN(Decentralized Physical Infrastructure Network) 데이터 센터를 구축하는 회사입니다. IPFS(InterPlanetary File System)와 Filecoin 기술을 활용하여 분산형 스토리지 네트워크를 운영하고 있으며, 기존 중앙집중식 클라우드 스토리지의 대안을 제시하고 있습니다.\n\n특히 NANODC라는 혁신적인 초소형 데이터센터 솔루션을 통해 3평 공간에 15kW 전력으로 운영 가능한 효율적인 인프라를 제공합니다. 제타큐브는 Web3와 AI 시대에 필수적인 분산형 데이터 인프라를 구축하여, 데이터 주권과 보안을 강화하면서도 경제적인 스토리지 솔루션을 제공하는 것을 목표로 하고 있습니다.';
    }

    // NanoDC 관련 키워드
    if (lowerMessage.includes('nanodc') || lowerMessage.includes('나노dc')) {
        return 'NANODC는 제타큐브가 개발한 3평 규모, 15kW 전력의 초소형 데이터센터 솔루션입니다. 스토리지, 서버, 네트워크, 전력, 냉각 시스템이 모두 통합된 Turn-Key 방식의 올인원 솔루션으로, 기존 대형 데이터센터 대비 공간과 전력 효율성이 뛰어납니다.\n\nIPFS와 Filecoin 기술을 기반으로 분산형 스토리지 네트워크를 구성하며, 누구나 쉽게 데이터센터 인프라를 구축하고 운영할 수 있도록 설계되었습니다. NANODC는 DePIN 네트워크의 핵심 노드로서 작동하며, Web3 생태계의 데이터 인프라 민주화에 기여하고 있습니다.';
    }

    return null;
}

async function simulateTypingResponse(text) {
    // 스트리밍처럼 보이게 텍스트를 조금씩 출력
    let messageElement = null;
    let currentText = '';

    // 텍스트를 청크로 나누기 (한글 고려)
    const chunkSize = 3;
    for (let i = 0; i < text.length; i += chunkSize) {
        const chunk = text.slice(i, i + chunkSize);
        currentText += chunk;

        if (!messageElement) {
            messageElement = addMessage('', 'assistant');
        }
        updateMessage(messageElement, currentText);

        // 약간의 딜레이로 타이핑 효과
        await new Promise(resolve => setTimeout(resolve, 30));
    }

    // 히스토리에 추가
    messageHistory.push({
        role: 'assistant',
        content: text
    });
}

async function sendMessageStream(messages, loadingElement) {
    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: messages,
                temperature: 0.7,
                max_tokens: 4096,  // 출력 토큰
                request_id: currentRequestId  // 요청 ID 전송
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        removeLoading(loadingElement);

        // 스트리밍 응답 처리
        currentReader = response.body.getReader();  // reader 저장 (중단용)
        const decoder = new TextDecoder();
        let assistantMessage = '';
        let messageElement = null;
        const thisRequestId = currentRequestId;  // 이 요청의 ID를 로컬 변수에 저장

        try {
            while (true) {
                const { done, value } = await currentReader.read();
                if (done) {
                    break;
                }

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        try {
                            const parsed = JSON.parse(data);

                            // 중단 신호 확인
                            if (parsed.stopped) {
                                break;
                            }

                            if (parsed.content) {
                                assistantMessage += parsed.content;

                                if (!messageElement) {
                                    messageElement = addMessage('', 'assistant');
                                    // 메시지 엘리먼트에 요청 ID 저장
                                    messageElement.dataset.requestId = thisRequestId;
                                }
                                await updateMessage(messageElement, assistantMessage);
                            }
                            if (parsed.error) {
                                console.error('서버 에러:', parsed.error);
                                throw new Error(parsed.error);
                            }
                        } catch (e) {
                            if (!e.message.includes('Unexpected token')) {
                                console.error('Parse error:', e, 'Data:', data);
                            }
                        }
                    }
                }
            }
        } catch (readError) {
            // Reader가 cancel되었을 때 발생하는 에러 무시 (중단 시)
            if (readError.name === 'TypeError' && readError.message.includes('null')) {
                console.log('스트림이 중단되었습니다.');
            } else if (readError.name !== 'AbortError') {
                // 중단이 아닌 다른 에러만 throw
                console.error('스트림 읽기 에러:', readError);
                throw readError;
            }
        }

        // 스트리밍 완료 후 차트 렌더링
        if (messageElement && assistantMessage) {
            await updateMessage(messageElement, assistantMessage, true);
        }

        // 히스토리에 추가
        if (assistantMessage) {
            messageHistory.push({
                role: 'assistant',
                content: assistantMessage
            });
        } else {
            console.warn('⚠️ 경고: 응답 메시지가 비어있습니다!');
            // 빈 응답일 경우 사용자에게 알림
            if (messageElement) {
                await updateMessage(messageElement, '응답을 받지 못했습니다. 다시 시도해주세요.');
            } else {
                showError('서버로부터 응답을 받지 못했습니다.');
            }
        }

    } catch (error) {
        // 중단으로 인한 에러는 무시
        if (error.name === 'AbortError' || error.message.includes('user aborted')) {
            console.log('요청이 사용자에 의해 중단되었습니다.');
            return;
        }
        throw error;
    }
}

// 일반 API 호출 (스트리밍 없음)
async function sendMessageNonStream(messages, loadingElement) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: messages,
                temperature: 0.7,
                max_tokens: 4096  // 출력 토큰
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        removeLoading(loadingElement);

        if (data.success) {
            addMessage(data.message, 'assistant');
            messageHistory.push({
                role: 'assistant',
                content: data.message
            });
        } else {
            throw new Error(data.error || '알 수 없는 오류가 발생했습니다.');
        }

    } catch (error) {
        throw error;
    }
}

function addMessage(content, role) {
    const chatContainer = document.getElementById('chatContainer');

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;

    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);

    // 스크롤을 아래로
    chatContainer.scrollTop = chatContainer.scrollHeight;

    return contentDiv;
}

async function updateMessage(element, content, isStreamingComplete = false) {
    // 이미 렌더링된 차트 보존
    const existingMermaidCharts = new Map();
    const existingChartjsCharts = new Map();

    if (typeof mermaid !== 'undefined') {
        const renderedMermaids = element.querySelectorAll('div.mermaid[data-processed="true"]');
        renderedMermaids.forEach((chart) => {
            const mermaidCode = chart.getAttribute('data-mermaid-code');
            if (mermaidCode) {
                existingMermaidCharts.set(mermaidCode, chart.cloneNode(true));
            }
        });
    }

    // Chart.js 차트 보존 (JSON 데이터만 저장, 차트는 재생성)
    const renderedChartjs = element.querySelectorAll('.chartjs-container');
    renderedChartjs.forEach((container) => {
        const chartData = container.getAttribute('data-chart-json');
        if (chartData) {
            // 차트 객체는 복사 불가능하므로 JSON 데이터만 저장
            existingChartjsCharts.set(chartData, chartData);
        }
    });

    // 마크다운을 HTML로 변환
    if (typeof marked !== 'undefined') {
        element.innerHTML = marked.parse(content);
    } else {
        element.textContent = content;
    }

    // Chart.js 차트 렌더링 - 스트리밍 완료 후에만 실행
    if (typeof Chart !== 'undefined' && isStreamingComplete) {
        const chartjsBlocks = element.querySelectorAll('pre code.language-chartjs');

        for (let index = 0; index < chartjsBlocks.length; index++) {
            const block = chartjsBlocks[index];
            const chartJson = block.textContent.trim();

            // JSON 유효성 검사
            let isValidJson = false;
            try {
                JSON.parse(chartJson);
                isValidJson = true;
            } catch (e) {
                // JSON이 유효하지 않음
                console.error('Invalid chart JSON:', e);
                continue;
            }

            if (!isValidJson) {
                continue;
            }

            // 이미 렌더링된 차트가 있으면 건너뛰기
            if (existingChartjsCharts.has(chartJson)) {
                continue;
            }

            try {
                const chartConfig = JSON.parse(chartJson);

                // 차트 컨테이너 생성
                const chartContainer = document.createElement('div');
                chartContainer.className = 'chartjs-container';
                chartContainer.setAttribute('data-chart-json', chartJson);

                // 로딩 스피너 추가
                const loadingSpinner = document.createElement('div');
                loadingSpinner.className = 'chart-loading';
                loadingSpinner.innerHTML = '<div class="spinner"></div><p>차트를 생성하는 중...</p>';
                chartContainer.appendChild(loadingSpinner);

                const canvas = document.createElement('canvas');
                canvas.id = `chart-${Date.now()}-${index}`;
                // 막대 그래프는 항목 수에 따라 높이 조정
                const canvasHeight = chartConfig.type === 'bar'
                    ? Math.max(400, chartConfig.labels.length * 30)
                    : 400;
                canvas.width = 600;
                canvas.height = canvasHeight;
                canvas.style.display = 'none'; // 처음에는 숨김
                chartContainer.appendChild(canvas);

                // <pre> 요소 교체
                const preElement = block.parentElement;
                preElement.parentElement.replaceChild(chartContainer, preElement);

                // Chart.js 설정
                const ctx = canvas.getContext('2d');

                // 색상 팔레트 (GS 리테일 테마)
                const colors = [
                    'rgba(255, 107, 0, 0.8)',   // GS Orange
                    'rgba(0, 170, 91, 0.8)',    // GS Green
                    'rgba(0, 102, 204, 0.8)',   // GS Blue
                    'rgba(255, 193, 7, 0.8)',   // Yellow
                    'rgba(220, 53, 69, 0.8)',   // Red
                    'rgba(108, 117, 125, 0.8)', // Gray
                    'rgba(111, 66, 193, 0.8)',  // Purple
                    'rgba(23, 162, 184, 0.8)',  // Cyan
                    'rgba(40, 167, 69, 0.8)',   // Green
                    'rgba(253, 126, 20, 0.8)'   // Orange
                ];

                const borderColors = colors.map(c => c.replace('0.8', '1'));

                // 막대 차트는 단일 색상 사용
                const backgroundColor = chartConfig.type === 'bar'
                    ? 'rgba(255, 107, 0, 0.8)'
                    : colors;
                const borderColor = chartConfig.type === 'bar'
                    ? 'rgba(255, 107, 0, 1)'
                    : borderColors;

                // 차트 생성 후 로딩 제거
                setTimeout(() => {
                    try {
                        new Chart(ctx, {
                            type: chartConfig.type,
                            data: {
                                labels: chartConfig.labels,
                                datasets: [{
                                    label: chartConfig.title,
                                    data: chartConfig.data,
                                    backgroundColor: backgroundColor,
                                    borderColor: borderColor,
                                    borderWidth: 2
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: {
                                        display: chartConfig.type === 'pie',
                                        position: 'bottom',
                                        labels: {
                                            font: {
                                                size: 13,
                                                family: "'Inter', sans-serif"
                                            },
                                            padding: 20,
                                            boxWidth: 15
                                        }
                                    },
                                    title: {
                                        display: true,
                                        text: chartConfig.title,
                                        font: {
                                            size: 18,
                                            weight: '600',
                                            family: "'Inter', sans-serif"
                                        },
                                        padding: 25
                                    }
                                },
                                scales: chartConfig.type === 'bar' ? {
                                    y: {
                                        beginAtZero: true,
                                        ticks: {
                                            font: {
                                                size: 12,
                                                family: "'Inter', sans-serif"
                                            }
                                        }
                                    },
                                    x: {
                                        ticks: {
                                            font: {
                                                size: 12,
                                                family: "'Inter', sans-serif"
                                            },
                                            maxRotation: 45,
                                            minRotation: 0
                                        }
                                    }
                                } : {}
                            }
                        });

                        // 로딩 스피너 제거하고 차트 표시
                        loadingSpinner.style.opacity = '0';
                        setTimeout(() => {
                            loadingSpinner.remove();
                            canvas.style.display = 'block';
                            canvas.style.opacity = '0';
                            setTimeout(() => {
                                canvas.style.transition = 'opacity 0.3s ease';
                                canvas.style.opacity = '1';
                            }, 10);
                        }, 300);
                    } catch (chartError) {
                        console.error('Chart 생성 실패:', chartError);
                        console.error('차트 설정:', chartConfig);
                        loadingSpinner.innerHTML = '<p style="color: #ff6b6b;">차트 생성 실패: ' + chartError.message + '</p>';
                    }
                }, 100);
            } catch (e) {
                console.error('Chart.js 렌더링 오류:', e);
                block.textContent = '차트 렌더링 오류: ' + e.message;
            }
        }
    }

    // Mermaid 차트 렌더링
    if (typeof mermaid !== 'undefined') {
        const mermaidBlocks = element.querySelectorAll('pre code.language-mermaid');

        for (let index = 0; index < mermaidBlocks.length; index++) {
            const block = mermaidBlocks[index];
            const mermaidCode = block.textContent.trim();

            // 최소 길이 체크 - 너무 짧으면 아직 스트리밍 중
            if (mermaidCode.length < 20) {
                continue;
            }

            // 이미 렌더링된 차트가 있으면 재사용
            if (existingMermaidCharts.has(mermaidCode)) {
                const cachedChart = existingMermaidCharts.get(mermaidCode);
                block.parentElement.replaceWith(cachedChart);
                continue;
            }

            // 새로운 차트 렌더링 (완성된 것만)
            const mermaidId = `mermaid-${Date.now()}-${index}`;
            const mermaidDiv = document.createElement('div');
            mermaidDiv.className = 'mermaid';
            mermaidDiv.id = mermaidId;

            // Mermaid 차트의 특수문자 오류 방지: 레이블 정리
            let sanitizedCode = mermaidCode;

            // xychart-beta의 x-axis 레이블 정리
            if (mermaidCode.includes('xychart-beta') && mermaidCode.includes('x-axis')) {
                sanitizedCode = sanitizedCode.replace(/x-axis\s+\[(.*?)\]/gs, (match, labels) => {
                    const cleanLabels = labels
                        .split(',')
                        .map(label => {
                            // 따옴표 제거 후 특수문자 제거 (한글, 영문, 숫자, 공백만 허용)
                            const trimmed = label.trim().replace(/['"]/g, '');
                            const cleaned = trimmed.replace(/[^가-힣a-zA-Z0-9\s]/g, '').trim();
                            return cleaned;
                        })
                        .filter(label => label.length > 0)
                        .join(', ');
                    return `x-axis [${cleanLabels}]`;
                });
            }

            // 파이 차트의 레이블 정리
            if (mermaidCode.includes('pie')) {
                sanitizedCode = sanitizedCode.replace(/"([^"]+)"\s*:\s*(\d+\.?\d*)/g, (match, label, value) => {
                    // 레이블에서 특수문자 제거 (한글, 영문, 숫자, 공백만 허용)
                    const cleaned = label.replace(/[^가-힣a-zA-Z0-9\s]/g, '').trim();
                    return `"${cleaned}" : ${value}`;
                });
            }

            mermaidDiv.textContent = sanitizedCode;
            mermaidDiv.setAttribute('data-mermaid-code', sanitizedCode);

            block.parentElement.replaceWith(mermaidDiv);

            try {
                await mermaid.run({ nodes: [mermaidDiv] });
            } catch (e) {
                console.error('Mermaid 렌더링 오류:', e);
                mermaidDiv.textContent = '차트 렌더링 오류: ' + e.message;
            }
        }
    }

    const chatContainer = document.getElementById('chatContainer');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showLoading() {
    const chatContainer = document.getElementById('chatContainer');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = 'loading-message';

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message-content';

    const loadingDots = document.createElement('div');
    loadingDots.className = 'loading';
    loadingDots.innerHTML = '<span></span><span></span><span></span>';

    loadingDiv.appendChild(loadingDots);
    messageDiv.appendChild(loadingDiv);
    chatContainer.appendChild(messageDiv);

    chatContainer.scrollTop = chatContainer.scrollHeight;

    return messageDiv;
}

function removeLoading(element) {
    if (element && element.parentNode) {
        element.parentNode.removeChild(element);
    }
}

function showError(message) {
    const chatContainer = document.getElementById('chatContainer');

    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = `오류: ${message}`;

    chatContainer.appendChild(errorDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function toggleButton(mode) {
    const actionButton = document.getElementById('actionButton');
    const sendIcon = document.getElementById('sendIcon');
    const stopIcon = document.getElementById('stopIcon');

    if (mode === 'send') {
        sendIcon.style.display = 'block';
        stopIcon.style.display = 'none';
        actionButton.disabled = false;
    } else if (mode === 'stop') {
        sendIcon.style.display = 'none';
        stopIcon.style.display = 'block';
        actionButton.disabled = false;
    } else if (mode === 'disabled') {
        actionButton.disabled = true;
    }
}

function handleAction() {
    if (isLoading) {
        // 로딩 중이면 중단
        stopGeneration();
    } else {
        // 아니면 메시지 전송
        sendMessage();
    }
}

async function stopGeneration() {
    if (!currentRequestId) {
        console.log('중단할 요청이 없습니다.');
        return;
    }

    console.log(`요청 ${currentRequestId} 중단 중...`);

    try {
        // Reader 취소
        if (currentReader) {
            await currentReader.cancel();
            console.log('Reader 취소됨');
        }

        // 백엔드에 중단 신호 전송
        const response = await fetch('/api/chat/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                request_id: currentRequestId
            })
        });

        const result = await response.json();
        console.log('중단 응답:', result);

        // UI 상태 복원
        isLoading = false;
        currentRequestId = null;
        currentReader = null;
        toggleButton('send');

    } catch (error) {
        console.error('중단 실패:', error);
    }
}

// 채팅 초기화 함수 (선택사항)
function clearChat() {
    messageHistory = [];
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = `
        <div class="welcome-message">
            <h2>시스템 준비 완료. 대화를 시작하세요.</h2>
            <div class="example-prompts">
                <button class="example-btn" onclick="sendExample('제타큐브는 어떤 회사야?')">💼 제타큐브 소개</button>
                <button class="example-btn" onclick="sendExample('NanoDC에 대해 알려줘')">🏢 NanoDC 설명</button>
                <button class="example-btn" onclick="sendExample('Vasp 라이센스가 뭐야?')">📜 Vasp 라이센스</button>
            </div>
        </div>
    `;
}

// 타이핑 효과 추가 (선택사항)
function typewriterEffect(element, text, speed = 30) {
    let i = 0;
    element.textContent = '';

    function type() {
        if (i < text.length) {
            element.textContent += text.charAt(i);
            i++;
            const chatContainer = document.getElementById('chatContainer');
            chatContainer.scrollTop = chatContainer.scrollHeight;
            setTimeout(type, speed);
        }
    }

    type();
}
