document.getElementById('uploadForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    // 【修复：上传新视频前清空旧的视频状态（保留文件选择）】
    currentVideoId = "";
    currentVideoUrl = "";
    uploadedVideoUrl = "";
    window.videoId = "";
    // 重置播放器（清空旧视频源）
    const previewVideoPlayer = document.getElementById('previewVideoPlayer');
    previewVideoPlayer.pause();
    previewVideoPlayer.src = '';
    previewVideoPlayer.load();
    // 清空按钮的旧视频ID
    document.getElementById('startAnalysisBtn').dataset.vid = "";


    const selectedSource = document.querySelector('input[name="videoSource"]:checked').value;
    const uploadBtn = document.getElementById('uploadBtn');
    const loadingArea = document.getElementById('loadingArea');
    const videoPreviewArea = document.getElementById('videoPreviewArea');
    const startAnalysisBtn = document.getElementById('startAnalysisBtn');
    const fileInfo = document.getElementById('fileInfo');
    uploadBtn.disabled = true;

    try {
        let response, result;
        hideAllAreas();
        loadingArea.style.display = 'block';

        // ========== 本地文件 ==========
        if (selectedSource === 'local') {
            const fileInput = document.getElementById('videoFileInput');
            if (!fileInput.files.length) {
                alert('请先选择本地视频文件');
                uploadBtn.disabled = false;
                loadingArea.style.display = 'none';
                return;
            }

            const formData = new FormData();
            formData.append('video', fileInput.files[0]);

            // Show the video preview immediately
            showVideoPreview(URL.createObjectURL(fileInput.files[0]));

            response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

        // ========== URL ==========
        } else {
            const videoUrl = document.getElementById('videoUrlInput').value.trim();
            if (!videoUrl) {
                alert('请输入视频 URL');
                uploadBtn.disabled = false;
                loadingArea.style.display = 'none';
                return;
            }

            response = await fetch('/upload', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ video_url: videoUrl })
            });
        }

        result = await response.json();

        if (!result.success) {
            throw new Error(result.message || '上传失败');
        }

        // This will continue in the background, independent of the preview process
        currentVideoId = result.video_id;
        currentVideoUrl = result.video_url;
        uploadedVideoUrl = result.video_url;
        window.videoId = result.video_id;
        document.getElementById('startAnalysisBtn').dataset.vid = result.video_id;

        // Show the video preview after download for URL-based videos
        if (selectedSource === 'url') {
            // 【修改1：重置播放器状态，避免残留错误】
            const previewVideoPlayer = document.getElementById('previewVideoPlayer');
            previewVideoPlayer.pause();
            previewVideoPlayer.src = '';
            previewVideoPlayer.load();

            // Assuming the video is downloaded successfully and a downloadable path is provided in `result.video_url`
            showVideoPreview(result.video_url);

            // 【修改2：补充URL视频的大小显示】
            document.getElementById('videoFileSize').textContent = '爬虫下载视频';
        }

        enableAnalysis();
    } catch (err) {
        console.error(err);
        showError(err.message || '视频处理失败');
        uploadBtn.disabled = false;
        fileInfo.innerHTML = selectedSource === 'local'
            ? '支持格式: MP4, AVI, MOV, MKV, WebM | 最大大小: 500MB'
            : '支持格式: 抖音/快手/小红书/B站等短视频URL | 请输入有效URL';
        fileInfo.style.color = '#7f8c8d';
        fileInfo.style.fontWeight = 'normal';
    } finally {
        loadingArea.style.display = 'none';
        uploadBtn.disabled = false;
    }
});

// ================== 视频预览 ==================
function showVideoPreview(videoUrl) {
    const previewArea = document.getElementById('videoPreviewArea');
    const video = document.getElementById('previewVideoPlayer');

    // 【修改3：强制重置播放器状态，适配URL视频】
    video.pause();
    video.src = '';
    video.load();

    // Set the source immediately and show the preview
    video.src = videoUrl;
    video.load();

    previewArea.style.display = 'block';

    video.onloadedmetadata = () => {
        document.getElementById('videoFileName').innerText = videoUrl.split('/').pop();
        // 【修改4：改用页面已有的formatVideoDuration函数，统一时长格式】
        document.getElementById('videoDuration').innerText = formatVideoDuration(video.duration);
        document.getElementById('videoDimensions').innerText =
            `${video.videoWidth}×${video.videoHeight}`;
        document.getElementById('videoFileSize').innerText = document.getElementById('videoFileSize').innerText || '--';

        // 【修改5：更新预览提示文本】
        document.querySelector('.video-tip').textContent = '✅ 视频加载完成，支持播放/暂停/进度条/音量控制';
    };

    // 【修改6：新增URL视频加载错误重试逻辑】
    video.addEventListener('error', function() {
        if (document.querySelector('input[name="videoSource"][value="url"]').checked) {
            console.error('URL视频预览重试:', videoUrl);
            document.querySelector('.video-tip').textContent = '⚠️ 视频正在加载（已下载完成）';
            setTimeout(() => {
                video.src = videoUrl;
                video.load();
            }, 1000);
        }
    });
}

// ================== 以下代码完全不变 ==================
function enableAnalysis() {
    const startBtn = document.getElementById('startAnalysisBtn');
    startBtn.disabled = false;
}

function showError(msg) {
    const errorArea = document.getElementById('errorArea');
    const errorContent = document.getElementById('errorContent');
    errorContent.innerText = msg;
    errorArea.style.display = 'block';
}

// 文件选择事件监听（原有逻辑，保持不变）
videoFileInput.addEventListener('change', function (e) {
    const file = e.target.files[0];
    if (!file) return;

    originalVideoFile = file;

    // 验证文件类型
    const validTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-matroska', 'video/webm'];
    if (!validTypes.some(type => file.type.includes(type.replace('video/', '')) ||
        file.name.toLowerCase().endsWith('.mp4') ||
        file.name.toLowerCase().endsWith('.avi') ||
        file.name.toLowerCase().endsWith('.mov') ||
        file.name.toLowerCase().endsWith('.mkv') ||
        file.name.toLowerCase().endsWith('.webm'))) {
        showError('请选择有效的视频文件 (MP4, AVI, MOV, MKV, WebM)');
        resetFileInput();
        return;
    }

    // 验证文件大小 (500MB)
    if (file.size > 500 * 1024 * 1024) {
        showError('文件太大，请选择小于500MB的视频文件');
        resetFileInput();
        return;
    }

    // 启用上传按钮
    uploadBtn.disabled = false;

    // 显示文件信息
    fileInfo.innerHTML = `已选择: ${file.name} | 大小: ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
    fileInfo.style.color = '#27ae60';
    fileInfo.style.fontWeight = '600';

    // 创建本地预览
    createLocalPreview(file);
});

// 创建本地预览（原有逻辑，保持不变）
function createLocalPreview(file) {
    // 释放之前的URL
    if (localVideoUrl) {
        URL.revokeObjectURL(localVideoUrl);
    }

    // 创建新的URL
    localVideoUrl = URL.createObjectURL(file);

    // 设置视频源
    previewVideoPlayer.src = localVideoUrl;
    previewVideoPlayer.load();

    // 显示视频信息
    videoFileName.textContent = file.name;
    videoFileSize.textContent = (file.size / (1024 * 1024)).toFixed(2) + ' MB';

    // 监听视频元数据加载
    previewVideoPlayer.addEventListener('loadedmetadata', function () {
        // 更新视频信息
        const duration = previewVideoPlayer.duration;
        const minutes = Math.floor(duration / 60);
        const seconds = Math.floor(duration % 60);
        videoDuration.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        videoDimensions.textContent = `${previewVideoPlayer.videoWidth}×${previewVideoPlayer.videoHeight}`;

        // 创建缩略图
        createVideoThumbnail();

        // 显示本地预览提示
        localPreviewInfo.style.display = 'block';

        // 显示视频预览区域
        videoPreviewArea.style.display = 'block';
    });

    // 监听视频错误
    previewVideoPlayer.addEventListener('error', function (e) {
        console.error('视频加载错误:', previewVideoPlayer.error);
        showError('视频预览加载失败，请确保视频格式正确');
    });

    // 监听视频可以播放
    previewVideoPlayer.addEventListener('canplay', function () {
        console.log('✅ 预览视频可以播放');
    });
}

// 创建视频缩略图（原有逻辑，保持不变）
function createVideoThumbnail() {
    // 创建一个canvas来捕获第一帧
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    canvas.width = previewVideoPlayer.videoWidth;
    canvas.height = previewVideoPlayer.videoHeight;

    // 尝试捕获第一帧
    previewVideoPlayer.currentTime = 0;

    previewVideoPlayer.addEventListener('seeked', function onSeeked() {
        ctx.drawImage(previewVideoPlayer, 0, 0, canvas.width, canvas.height);
        videoThumbnail.src = canvas.toDataURL('image/jpeg');
        previewVideoPlayer.removeEventListener('seeked', onSeeked);
    });
}

// 重置文件输入（原有逻辑，保持不变）
function resetFileInput() {
    videoFileInput.value = '';
    uploadBtn.disabled = true;
    fileInfo.innerHTML = '支持格式: MP4, AVI, MOV, MKV, WebM | 最大大小: 500MB';
    fileInfo.style.color = '#7f8c8d';
    fileInfo.style.fontWeight = 'normal';
    localPreviewInfo.style.display = 'none';
    videoPreviewArea.style.display = 'none';
    startAnalysisBtn.disabled = true;
    originalVideoFile = null;
}

// 重置到上传状态（原有逻辑 + 修复videoId清空）
function resetToUpload() {
    hideAllAreas();
    resetFileInput();
    uploadForm.style.display = 'block';

    // 释放本地视频URL
    if (localVideoUrl) {
        URL.revokeObjectURL(localVideoUrl);
        localVideoUrl = null;
    }

    // 重置分析相关状态 【核心修复：清空所有videoId存储】
    currentVideoId = "";
    window.videoId = "";
    document.getElementById('startAnalysisBtn').dataset.vid = "";
    frameList = [];
    currentFrameIndex = 0;
    analysisComplete = false;
    uploadedVideoUrl = null;

    // 重置按钮状态
    startAnalysisBtn.disabled = true;
    startAnalysisBtn.style.display = 'inline-flex';
    stopAnalysisContainer.style.display = 'none';

    // 清空帧列表
    frameListEl.innerHTML = '<div style="text-align: center; width: 100%; padding: 40px; color: #7f8c8d;">分析完成后，帧列表将显示在这里</div>';

    // 重置帧显示
    currentFrameImg.src = "";
    frameIndex.textContent = "0/0";
    frameHorror.textContent = "0.00%";
    frameViolence.textContent = "0.00%";
    frameNsfw.textContent = "0.000%";
    frameIsRisk.textContent = "安全";
    frameIsRisk.className = "stat-value stat-safe";
    frameSingleDuration.textContent = "0.0000 秒";
    frameTag.textContent = "安全帧";
    frameTag.className = "frame-tag tag-safe";

    // 禁用帧控制按钮
    prevFrameBtn.disabled = true;
    nextFrameBtn.disabled = true;
    playFrameBtn.disabled = true;

    // 关闭SSE连接
    if (currentSSE) {
        currentSSE.close();
        currentSSE = null;
    }

    // 清空完整视频播放器
    fullVideoPlayer.src = "";
    fullVideoLoading.style.display = 'none';
    fullVideoTip.style.display = 'none';

    // 销毁所有图表实例
    destroyAllCharts();
}

// 销毁所有图表实例（原有逻辑，保持不变）
function destroyAllCharts() {
    if (riskTimelineChart) {
        riskTimelineChart.destroy();
        riskTimelineChart = null;
    }
    if (riskCategoryChart) {
        riskCategoryChart.destroy();
        riskCategoryChart = null;
    }
    if (frameStatsChart) {
        frameStatsChart.destroy();
        frameStatsChart = null;
    }
    if (performanceChart) {
        performanceChart.destroy();
        performanceChart = null;
    }
    console.log('✅ 所有图表已销毁');
}

// 检查浏览器是否支持SSE（原有逻辑，保持不变）
if (!window.EventSource) {
    showError('您的浏览器不支持Server-Sent Events (SSE)，请使用Chrome、Firefox或Edge等现代浏览器');
}

// 开始分析按钮点击事件 【核心修复：稳健获取videoId】
startAnalysisBtn.addEventListener('click', () => {
    // 三重兜底获取 永不丢失
    const vid = window.videoId || currentVideoId || document.getElementById('startAnalysisBtn').dataset.vid;
    if (!vid) {
        showError('未检测到视频，请重新上传');
        return;
    }

    startAnalysisBtn.disabled = true;
    startAnalysisSSE(vid);
});

// 停止分析按钮（原有逻辑，保持不变）
stopAnalysisBtn.addEventListener('click', () => {
    if (currentSSE) {
        currentSSE.close();
        currentSSE = null;
        console.log('用户手动停止分析');

        startAnalysisBtn.disabled = false;
        stopAnalysisContainer.style.display = 'none';

        hideAllAreas();
        videoPreviewArea.style.display = 'block';
    }
});

// 重置按钮（原有逻辑，保持不变）
resetBtn.addEventListener('click', resetToUpload);