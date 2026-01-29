function showError(message) {
    console.error('显示错误:', message);
    hideAllAreas();
    errorArea.style.display = 'block';
    document.getElementById('errorContent').textContent = message;

    // 重置按钮状态
    startAnalysisBtn.disabled = false;
    stopAnalysisContainer.style.display = 'none';

    // 关闭SSE连接
    if (currentSSE) {
        currentSSE.close();
        currentSSE = null;
    }
}

// 隐藏所有区域
function hideAllAreas() {
    videoPreviewArea.style.display = 'none';
    progressArea.style.display = 'none';
    stopAnalysisContainer.style.display = 'none';
    framePreviewArea.style.display = 'none';
    resultArea.style.display = 'none';
    loadingArea.style.display = 'none';
    errorArea.style.display = 'none';
    fullVideoSection.style.display = 'none';
}