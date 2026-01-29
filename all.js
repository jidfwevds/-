// 全局变量
let currentVideoId = "";
let frameList = [];
let currentFrameIndex = 0;
let framePlayTimer = null;
let isPlaying = false;
let currentSSE = null;
let analysisComplete = false;
let currentBatchInfo = "";
let connectionStatus = "disconnected";
let localVideoUrl = null;
let uploadedVideoUrl = null; // 存储上传后的视频URL
let originalVideoFile = null; // 存储原始视频文件

// 图表实例（适配你的HTML中所有图表）
let riskTimelineChart = null;    // 时序风险波动图
let riskCategoryChart = null;    // 风险类别雷达图
let frameStatsChart = null;      // 视频帧统计图
let performanceChart = null;     // 性能指标图

// DOM元素获取
const uploadForm = document.getElementById('uploadForm');
const videoFileInput = document.getElementById('videoFileInput');
const uploadBtn = document.getElementById('uploadBtn');
const fileInfo = document.getElementById('fileInfo');
const localPreviewInfo = document.getElementById('localPreviewInfo');
const videoPreviewArea = document.getElementById('videoPreviewArea');
const previewVideoPlayer = document.getElementById('previewVideoPlayer');
const videoThumbnail = document.getElementById('videoThumbnail');
const videoFileName = document.getElementById('videoFileName');
const videoFileSize = document.getElementById('videoFileSize');
const videoDuration = document.getElementById('videoDuration');
const videoDimensions = document.getElementById('videoDimensions');
const startAnalysisBtn = document.getElementById('startAnalysisBtn');
const stopAnalysisBtn = document.getElementById('stopAnalysisBtn');
const resetBtn = document.getElementById('resetBtn');
const progressArea = document.getElementById('progressArea');
const progressTitle = document.getElementById('progressTitle');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const performanceInfo = document.getElementById('performanceInfo');
const progressStatus = document.getElementById('progressStatus');
const framePreviewArea = document.getElementById('framePreviewArea');
const currentFrameImg = document.getElementById('currentFrameImg');
const frameTag = document.getElementById('frameTag');
const prevFrameBtn = document.getElementById('prevFrameBtn');
const nextFrameBtn = document.getElementById('nextFrameBtn');
const playFrameBtn = document.getElementById('playFrameBtn');
const frameListEl = document.getElementById('frameList');
const frameIndex = document.getElementById('frameIndex');
const frameHorror = document.getElementById('frameHorror');
const frameViolence = document.getElementById('frameViolence');
const frameNsfw = document.getElementById('frameNsfw');
const frameIsRisk = document.getElementById('frameIsRisk');
const frameSingleDuration = document.getElementById('frameSingleDuration');
const resultArea = document.getElementById('resultArea');
const loadingArea = document.getElementById('loadingArea');
const errorArea = document.getElementById('errorArea');
const fullVideoSection = document.getElementById('fullVideoSection');
const fullVideoPlayer = document.getElementById('fullVideoPlayer');
const fullVideoLoading = document.getElementById('fullVideoLoading');
const fullVideoTip = document.getElementById('fullVideoTip');
const analysisStatus = document.getElementById('analysisStatus');
const retryFullVideoBtn = document.getElementById('retryFullVideoBtn');
const stopAnalysisContainer = document.getElementById('stopAnalysisContainer');

// 等待DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 绑定错误区域的重试按钮
    const retryBtn = document.getElementById('retryBtn');
    if (retryBtn) {
        retryBtn.addEventListener('click', resetToUpload);
    }
    console.log('✅ DOM加载完成，初始化完成');
});

// 文件选择事件监听
videoFileInput.addEventListener('change', function (e) {
    const file = e.target.files[0];
    if (!file) return;

    originalVideoFile = file; // 保存原始文件

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

// 创建本地预览
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

// 创建视频缩略图
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

// 重置文件输入
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

// 重置到上传状态
function resetToUpload() {
    hideAllAreas();
    resetFileInput();
    uploadForm.style.display = 'block';

    // 释放本地视频URL
    if (localVideoUrl) {
        URL.revokeObjectURL(localVideoUrl);
        localVideoUrl = null;
    }

    // 重置分析相关状态
    currentVideoId = "";
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

    // 销毁所有图表实例（关键修正）
    destroyAllCharts();
}

// 销毁所有图表实例
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

// 检查浏览器是否支持SSE
if (!window.EventSource) {
    showError('您的浏览器不支持Server-Sent Events (SSE)，请使用Chrome、Firefox或Edge等现代浏览器');
}

// 上传视频处理
uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(uploadForm);
    const file = videoFileInput.files[0];

    if (!file) {
        showError('请选择视频文件');
        return;
    }

    hideAllAreas();
    loadingArea.style.display = 'block';

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            currentVideoId = data.video_id;

            // 保存上传后的视频URL（如果有的话）
            if (data.video_url) {
                uploadedVideoUrl = data.video_url;
            }

            // 隐藏加载区域，显示视频预览
            loadingArea.style.display = 'none';
            videoPreviewArea.style.display = 'block';

            // 启用开始分析按钮
            startAnalysisBtn.disabled = false;

            console.log('✅ 视频上传成功，ID:', currentVideoId);
        } else {
            showError(data.message || '视频上传失败');
        }
    } catch (err) {
        console.error('上传失败:', err);
        showError('视频上传失败：' + err.message);
    }
});

// 开始分析按钮点击事件
startAnalysisBtn.addEventListener('click', () => {
    if (!currentVideoId) {
        showError('未检测到视频，请重新上传');
        return;
    }

    // 禁用开始分析按钮
    startAnalysisBtn.disabled = true;

    startAnalysisSSE(currentVideoId);
});

// 停止分析按钮
stopAnalysisBtn.addEventListener('click', () => {
    if (currentSSE) {
        currentSSE.close();
        currentSSE = null;
        console.log('用户手动停止分析');

        // 恢复按钮状态
        startAnalysisBtn.disabled = false;
        stopAnalysisContainer.style.display = 'none';

        hideAllAreas();
        videoPreviewArea.style.display = 'block';
    }
});

// 重置按钮
resetBtn.addEventListener('click', resetToUpload);

// 分析视频的SSE连接
function startAnalysisSSE(videoId) {
    console.log('开始SSE分析，videoId:', videoId);

    // 重置状态
    frameList = [];
    currentFrameIndex = 0;
    analysisComplete = false;
    currentBatchInfo = "";
    connectionStatus = "connecting";

    // 重置UI
    hideAllAreas();
    progressArea.style.display = 'block';
    stopAnalysisContainer.style.display = 'block'; // 显示停止分析按钮
    progressFill.style.width = '0%';
    progressText.textContent = '当前进度：0%';
    performanceInfo.textContent = '';
    frameListEl.innerHTML = '';

    // 销毁旧图表
    destroyAllCharts();

    // 如果已有SSE连接，先关闭
    if (currentSSE) {
        currentSSE.close();
        currentSSE = null;
    }

    // 创建EventSource
    currentSSE = new EventSource(`/analyze-sse?video_id=${encodeURIComponent(videoId)}&t=${Date.now()}`);
    connectionStatus = "connected";

    console.log('SSE连接已创建');

    // 连接建立事件
    currentSSE.addEventListener('open', function (event) {
        console.log('SSE连接已打开');
        progressText.textContent = '连接已建立，开始分析...';
    });

    // 进度更新事件
    currentSSE.addEventListener('progress', function (event) {
        try {
            const progressData = JSON.parse(event.data);
            console.log('进度更新:', progressData);

            const progressPercent = Math.min(100, progressData.progress || 0);
            progressFill.style.width = progressPercent + '%';
            progressTitle.firstElementChild.textContent = progressData.title || '处理中...';
            progressText.innerHTML = `当前进度：${progressPercent.toFixed(1)}% (${progressData.current || 0}/${progressData.total || 0})`;

            if (progressData.current_fps) {
                performanceInfo.textContent = `当前FPS: ${progressData.current_fps.toFixed(2)}`;
            }

            if (progressData.batch_size) {
                currentBatchInfo = `批次大小: ${progressData.batch_size}`;
            }

        } catch (error) {
            console.error('解析进度数据出错:', error, event.data);
        }
    });

    // 帧结果事件
    currentSSE.addEventListener('frame', function (event) {
        try {
            const frameData = JSON.parse(event.data);
            frameList.push(frameData);

            console.log(`收到帧 ${frameData.frame_index}, 恐怖:${frameData.horror}%, 暴力:${frameData.violence}%, 色情:${frameData.nsfw}%`);

            // 清除默认提示
            if (frameList.length === 1) {
                frameListEl.innerHTML = '';
            }

            // 创建帧缩略图
            const thumbnail = document.createElement('img');
            thumbnail.className = `frame-thumbnail ${frameData.is_risk ? 'risk' : ''}`;
            thumbnail.src = `data:image/jpeg;base64,${frameData.frame_base64}`;
            thumbnail.dataset.index = frameList.length - 1;
            thumbnail.title = `帧 ${frameData.frame_index}\n恐怖: ${frameData.horror}%\n暴力: ${frameData.violence}%\n色情: ${frameData.nsfw}%`;
            thumbnail.addEventListener('click', () => {
                showFrame(frameList.length - 1);
            });
            frameListEl.appendChild(thumbnail);

            // 如果是第一帧，显示帧预览区域
            if (frameList.length === 1) {
                framePreviewArea.style.display = 'block';
                showFrame(0);

                // 启用帧控制按钮
                prevFrameBtn.disabled = false;
                nextFrameBtn.disabled = false;
                playFrameBtn.disabled = false;
            }

            // 自动滚动到最新的缩略图
            frameListEl.scrollLeft = frameListEl.scrollWidth;

        } catch (error) {
            console.error('解析帧数据出错:', error, event.data);
        }
    });

    // 分析完成事件
    currentSSE.addEventListener('complete', function (event) {
        try {
            console.log('收到完成事件');
            const resultData = JSON.parse(event.data);

            console.log('完成数据:', resultData);

            // 标记分析完成
            analysisComplete = true;
            connectionStatus = "completed";

            // 显示最终结果
            displayFinalResults(resultData);

            // 绘制所有图表（关键修正：适配你的HTML容器）
            if (frameList.length > 0) {
                renderRiskTimelineChart(resultData);    // 时序风险波动图
                renderRiskCategoryChart(resultData);    // 风险类别雷达图

            } else {
                console.warn('⚠️ 无帧数据，跳所有图表绘制');
            }

            // 更新UI
            progressFill.style.width = '100%';
            progressTitle.firstElementChild.textContent = '分析完成';
            progressText.textContent = '分析完成！';
            progressStatus.style.display = 'none';

            // 显示结果区域
            setTimeout(() => {
                progressArea.style.display = 'none';
                stopAnalysisContainer.style.display = 'none'; // 隐藏停止分析按钮
                resultArea.style.display = 'block';
                framePreviewArea.style.display = 'block';
                startAnalysisBtn.disabled = false;

                // 加载完整视频 - 使用预览视频的相同逻辑
                loadFullVideo();
            }, 1000);

            console.log('✅ 分析流程完成');

        } catch (error) {
            console.error('解析完成数据出错:', error, event.data);
            showError('解析结果时出错: ' + error.message);
        } finally {
            if (currentSSE) {
                currentSSE.close();
                currentSSE = null;
            }
        }
    });

    // 错误事件
    currentSSE.addEventListener('error', function (event) {
        console.error('SSE错误事件:', event);

        // 如果已经完成分析，忽略错误
        if (analysisComplete) {
            console.log('分析已完成，忽略错误');
            return;
        }

        // 如果有数据，解析错误信息
        if (event.data) {
            try {
                const errorData = JSON.parse(event.data);
                console.error('服务器返回错误:', errorData);
                showError('分析错误: ' + errorData.message);
            } catch (parseError) {
                console.error('解析错误数据失败:', parseError);
                showError('分析过程中发生错误');
            }
        } else {
            // 检查连接状态
            if (currentSSE && currentSSE.readyState === EventSource.CLOSED) {
                console.log('SSE连接已关闭');

                // 如果还没有收到完成事件，显示错误
                if (!analysisComplete) {
                    setTimeout(() => {
                        if (!analysisComplete) {
                            showError('连接已断开，请重试分析');
                        }
                    }, 1000);
                }
            }
        }
    });

    // 原生错误处理
    currentSSE.onerror = function (error) {
        console.error('EventSource原生错误:', error);

        // 如果已经完成分析，忽略错误
        if (analysisComplete) {
            return;
        }

        // 检查连接状态
        if (currentSSE && currentSSE.readyState === EventSource.CLOSED && !analysisComplete) {
            console.log('连接意外关闭');
            showError('连接意外断开，请重试分析');
        }
    };

    // 监听页面卸载，关闭SSE连接
    window.addEventListener('beforeunload', function () {
        if (currentSSE) {
            currentSSE.close();
            currentSSE = null;
        }

        // 释放本地视频URL
        if (localVideoUrl) {
            URL.revokeObjectURL(localVideoUrl);
        }

        // 销毁图表
        destroyAllCharts();
    });
}

// 加载完整视频 - 使用预览视频的相同逻辑
function loadFullVideo() {
    console.log('开始加载完整视频...');

    // 显示加载中状态
    fullVideoLoading.style.display = 'block';
    fullVideoTip.style.display = 'none';
    fullVideoSection.style.display = 'block';

    // 清除之前的事件监听器
    fullVideoPlayer.onloadeddata = null;
    fullVideoPlayer.onerror = null;

    // 方案1: 如果有上传后的视频URL，使用它
    if (uploadedVideoUrl) {
        console.log('使用上传后的视频URL:', uploadedVideoUrl);
        fullVideoPlayer.src = uploadedVideoUrl;
    }
    // 方案2: 使用本地预览视频（如果存在）
    else if (localVideoUrl) {
        console.log('使用本地预览视频URL');
        fullVideoPlayer.src = localVideoUrl;
    }
    // 方案3: 尝试从后端获取视频
    else if (currentVideoId) {
        console.log('尝试从后端获取视频，videoId:', currentVideoId);
        // 这里可以根据后端API获取视频URL
        // 例如: /video/${currentVideoId}
        // fullVideoPlayer.src = `/video/${currentVideoId}`;

        // 暂时使用本地预览（如果有的话）
        if (originalVideoFile) {
            const url = URL.createObjectURL(originalVideoFile);
            fullVideoPlayer.src = url;
            console.log('使用原始文件创建对象URL');
        } else {
            console.log('没有可用的视频源');
            fullVideoLoading.style.display = 'none';
            fullVideoTip.textContent = '❌ 无法加载完整视频，视频源不可用';
            fullVideoTip.style.color = '#e74c3c';
            fullVideoTip.style.display = 'block';
            return;
        }
    }

    // 监听视频加载完成
    fullVideoPlayer.addEventListener('loadeddata', function () {
        console.log('✅ 完整视频加载完成');
        fullVideoLoading.style.display = 'none';
        fullVideoTip.style.display = 'block';
        fullVideoTip.textContent = '✅ 完整视频加载完成，支持播放/暂停/进度条/音量控制';
        fullVideoTip.style.color = '#27ae60';

        // 确保视频可以播放
        fullVideoPlayer.play().catch(err => {
            console.log('自动播放被阻止，用户需要手动点击播放:', err);
        });
    });

    // 监听视频错误
    fullVideoPlayer.addEventListener('error', function (e) {
        console.error('完整视频加载错误:', fullVideoPlayer.error);
        fullVideoLoading.style.display = 'none';
        fullVideoTip.textContent = '❌ 视频加载失败，请尝试重新加载或联系管理员';
        fullVideoTip.style.color = '#e74c3c';
        fullVideoTip.style.display = 'block';

        // 显示错误详情
        const error = fullVideoPlayer.error;
        if (error) {
            let errorMsg = `错误代码: ${error.code}`;
            switch (error.code) {
                case MediaError.MEDIA_ERR_ABORTED:
                    errorMsg += ' (视频加载被中止)';
                    break;
                case MediaError.MEDIA_ERR_NETWORK:
                    errorMsg += ' (网络错误)';
                    break;
                case MediaError.MEDIA_ERR_DECODE:
                    errorMsg += ' (视频解码错误)';
                    break;
                case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
                    errorMsg += ' (视频格式不支持)';
                    break;
            }
            console.error('视频错误详情:', errorMsg);
        }
    });

    // 加载视频
    fullVideoPlayer.load();

    // 添加一个超时检查
    setTimeout(() => {
        if (fullVideoPlayer.readyState === 0) {
            console.log('视频加载超时，尝试使用本地文件...');

            // 尝试使用本地文件
            if (originalVideoFile && !fullVideoPlayer.src.includes('blob:')) {
                const url = URL.createObjectURL(originalVideoFile);
                fullVideoPlayer.src = url;
                fullVideoPlayer.load();
            }
        }
    }, 3000);
}

// 重新加载完整视频按钮
retryFullVideoBtn.addEventListener('click', () => {
    loadFullVideo();
});

// 显示最终结果的函数
function displayFinalResults(resultData) {
    console.log('显示最终结果:', resultData);

    // 更新风险等级显示
    const riskLevel = resultData.risk_level || '未知';
    const riskScore = resultData.risk_score || 0;
    const riskDesc = resultData.risk_desc || '';

    // 根据风险等级设置颜色
    let riskColor;
    switch (riskLevel) {
        case '安全':
            riskColor = '#27ae60';
            break;
        case '低风险':
            riskColor = '#3498db';
            break;
        case '中风险':
            riskColor = '#f39c12';
            break;
        case '高风险':
            riskColor = '#e74c3c';
            break;
        default:
            riskColor = '#95a5a6';
    }

    // 更新风险显示
    const riskLevelElement = document.getElementById('totalRiskLevel');
    riskLevelElement.textContent = riskLevel;
    riskLevelElement.style.color = riskColor;

    document.getElementById('totalRiskScore').textContent = riskScore.toFixed(2);
    document.getElementById('totalRiskDesc').textContent = riskDesc;

    // 更新统计信息
    document.getElementById('totalFrames').textContent = resultData.total_frames || 0;
    document.getElementById('analyzedFrames').textContent = resultData.analyzed_frames || 0;
    document.getElementById('riskFrames').textContent = resultData.risk_frames || 0;
    const riskRatioValue = resultData.risk_ratio ? (resultData.risk_ratio * 100) : 0;
    document.getElementById('riskRatio').textContent = riskRatioValue.toFixed(2) + '%';
    document.getElementById('avgHorror').textContent = (resultData.avg_horror || 0).toFixed(2) + '%';
    document.getElementById('avgViolence').textContent = (resultData.avg_violence || 0).toFixed(2) + '%';
    document.getElementById('avgNsfw').textContent = (resultData.avg_nsfw || 0).toFixed(3) + '%';

    // 更新视频信息
    document.getElementById('videoResolution').textContent = resultData.video_resolution || '未知';
    document.getElementById('videoResultDuration').textContent = (resultData.video_duration || 0).toFixed(2);
    document.getElementById('videoFps').textContent = (resultData.video_fps || 0).toFixed(2);

    // 更新性能信息
    const perf = resultData.batch_performance || {};
    document.getElementById('totalDuration').textContent = (resultData.total_duration || 0).toFixed(2);
    document.getElementById('inferDuration').textContent = (perf.total_inference_time_seconds || 0).toFixed(2);
    document.getElementById('batchCount').textContent = perf.total_batches || 0;
    document.getElementById('avgInferTime').textContent = (perf.avg_inference_time_per_frame_ms || 0).toFixed(2);
    document.getElementById('inferenceFps').textContent = (perf.inference_fps || 0).toFixed(2);
    document.getElementById('overallFps').textContent = (perf.overall_fps || 0).toFixed(2);
    document.getElementById('batchEfficiency').textContent = (perf.batch_efficiency_percent || 0).toFixed(1);
    document.getElementById('deviceInfo').textContent = perf.device || 'CPU';
}
function renderRiskTimelineChart(resultData) {
    // 检查容器是否存在
    const chartCanvas = document.getElementById('riskTimelineChart');
    if (!chartCanvas || frameList.length === 0) {
        console.warn('⚠️ 时序图容器不存在或无帧数据，跳过时序图绘制');
        return;
    }

    // 销毁旧图表
    if (riskTimelineChart) {
        riskTimelineChart.destroy();
    }

    // 提取数据
    const frameIndices = frameList.map((frame, index) => index + 1); // 帧索引（从1开始）
    const horrorScores = frameList.map(frame => frame.horror || 0); // 恐怖分值
    const violenceScores = frameList.map(frame => frame.violence || 0); // 暴力分值
    const nsfwScores = frameList.map(frame => frame.nsfw || 0); // NSFW分值
    const riskFlags = frameList.map(frame => frame.is_risk ? 1 : 0); // 违规标记（1=违规，0=安全）

    // 创建图表
    riskTimelineChart = new Chart(chartCanvas, {
        type: 'line',
        data: {
            labels: frameIndices,
            datasets: [
                {
                    label: '恐怖分值 (%)',
                    data: horrorScores,
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 2,
                    tension: 0.2,
                    fill: false
                },
                {
                    label: '暴力分值 (%)',
                    data: violenceScores,
                    borderColor: '#f39c12',
                    backgroundColor: 'rgba(243, 156, 18, 0.1)',
                    borderWidth: 2,
                    tension: 0.2,
                    fill: false
                },
                {
                    label: '色情分值 (‰)',
                    data: nsfwScores,
                    borderColor: '#9b59b6',
                    backgroundColor: 'rgba(155, 89, 182, 0.1)',
                    borderWidth: 2,
                    tension: 0.2,
                    fill: false
                },
                {
                    label: '违规标记',
                    data: riskFlags,
                    borderColor: '#34495e',
                    backgroundColor: 'rgba(52, 73, 94, 0.1)',
                    borderWidth: 1,
                    tension: 0,
                    fill: true,
                    pointRadius: 2,
                    pointStyle: riskFlags.map(flag => flag ? 'circle' : 'cross'),
                    yAxisID: 'y1' // 单独的Y轴
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true, // 关键：恢复宽高比保持，不再无限拉伸
            aspectRatio: 2.5, // 宽高比 2.5:1，控制垂直高度
            interaction: {
                mode: 'index',
                intersect: false,
            },
            layout: {
                padding: {
                    top: 10,
                    bottom: 10,
                    left: 5,
                    right: 5 // 减少左右padding
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: '帧索引',
                        padding: { top: 5 } // 减少标题padding
                    },
                    ticks: {
                        autoSkip: true,
                        maxTicksLimit: 15, // 减少X轴刻度数量（原20→15）
                        maxRotation: 0, // 禁止刻度旋转
                        padding: 5
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)',
                        drawBorder: false // 隐藏X轴边框
                    },
                    padding: { top: 5, bottom: 5 }
                },
                y: {
                    title: {
                        display: true,
                        text: '分值 (%)',
                        padding: { right: 5 }
                    },
                    min: 0,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        },
                        stepSize: 20, // 减少Y轴刻度数量
                        padding: 5
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)',
                        drawBorder: false
                    },
                    padding: { top: 5, bottom: 5 }
                },
                y1: {
                    position: 'right',
                    title: {
                        display: true,
                        text: '违规标记',
                        padding: { left: 5 }
                    },
                    min: -0.1,
                    max: 1.1,
                    ticks: {
                        stepSize: 1,
                        callback: function(value) {
                            return value === 1 ? '违规' : value === 0 ? '安全' : '';
                        },
                        padding: 5
                    },
                    grid: {
                        drawOnChartArea: false
                    },
                    padding: { top: 5, bottom: 5 }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        font: { size: 12 },
                        padding: 10, // 减少图例间距
                        usePointStyle: true, // 使用点样式代替方块，减少空间
                        pointStyle: 'circle'
                    },
                    padding: { bottom: 5 }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 10, // 减少tooltip内边距
                    cornerRadius: 6,
                    titleFont: { size: 13, weight: 'bold' },
                    bodyFont: { size: 12 },
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            if (context.parsed.y !== null) {
                                if (context.datasetIndex === 3) {
                                    label += context.parsed.y === 1 ? '违规' : '安全';
                                } else if (context.datasetIndex === 2) {
                                    label += context.parsed.y.toFixed(2) + '‰';
                                } else {
                                    label += context.parsed.y.toFixed(2) + '%';
                                }
                            }
                            return label;
                        },
                        title: function(context) {
                            return `帧 ${context[0].label}`;
                        }
                    }
                },
                title: {
                    display: true,
                    text: '视频帧风险分值时序波动图',
                    font: { size: 16, weight: 'bold' },
                    padding: { top: 5, bottom: 10 } // 减少标题上下padding
                }
            },
            animation: {
                duration: 800, // 缩短动画时长
                easing: 'easeOutQuart'
            },
            elements: {
                point: {
                    hoverRadius: 5, // 缩小hover点大小
                    hoverBorderWidth: 2,
                    radius: 1 // 缩小常规点大小
                }
            }
        }
    });

    console.log('✅ 时序风险波动图绘制完成');
}

// 2. 绘制风险类别雷达图
function renderRiskCategoryChart(resultData) {
    const chartCanvas = document.getElementById('riskCategoryChart');
    if (!chartCanvas) {
        console.warn('⚠️ 雷达图容器不存在，跳过雷达图绘制');
        return;
    }

    // 销毁旧图表
    if (riskCategoryChart) {
        riskCategoryChart.destroy();
    }

    // 提取平均分值
    const avgHorror = resultData.avg_horror || 0;
    const avgViolence = resultData.avg_violence || 0;
    const avgNsfw = resultData.avg_nsfw || 0;
    const riskThreshold = 50; // 风险阈值

    // 创建雷达图
    riskCategoryChart = new Chart(chartCanvas, {
        type: 'radar',
        data: {
            labels: ['恐怖风险', '暴力风险', '色情风险'],
            datasets: [
                {
                    label: '平均风险分值',
                    data: [avgHorror, avgViolence, avgNsfw],
                    backgroundColor: 'rgba(52, 152, 219, 0.2)',
                    borderColor: '#3498db',
                    pointBackgroundColor: '#3498db',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: '#3498db'
                },
                {
                    label: '风险阈值',
                    data: [riskThreshold, riskThreshold, riskThreshold],
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderColor: '#e74c3c',
                    borderDash: [5, 5],
                    pointBackgroundColor: '#e74c3c',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: '#e74c3c',
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    suggestedMin: 0,
                    suggestedMax: 100,
                    ticks: {
                        stepSize: 20,
                        callback: function(value) {
                            return value + '%';
                        }
                    },
                    pointLabels: {
                        font: {
                            size: 14,
                            weight: 'bold'
                        },
                        padding: 20
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            const label = context.dataset.label || '';
                            return `${label}: ${context.parsed.r.toFixed(2)}%`;
                        }
                    }
                },
                title: {
                    display: true,
                    text: '视频风险类别雷达图',
                    font: {
                        size: 16,
                        weight: 'bold'
                    },
                    padding: {
                        top: 10,
                        bottom: 20
                    }
                }
            },
            animation: {
                duration: 1000,
                easing: 'easeOutQuart'
            }
        }
    });

    console.log('✅ 风险类别雷达图绘制完成');
}

// 上一帧
prevFrameBtn.addEventListener('click', () => {
    if (currentFrameIndex > 0) {
        showFrame(currentFrameIndex - 1);
    }
});

// 下一帧
nextFrameBtn.addEventListener('click', () => {
    if (currentFrameIndex < frameList.length - 1) {
        showFrame(currentFrameIndex + 1);
    }
});

// 播放/暂停帧
playFrameBtn.addEventListener('click', () => {
    if (isPlaying) {
        clearInterval(framePlayTimer);
        playFrameBtn.textContent = '▶️';
        isPlaying = false;
    } else {
        playFrameBtn.textContent = '⏸️';
        isPlaying = true;
        framePlayTimer = setInterval(() => {
            if (currentFrameIndex >= frameList.length - 1) {
                currentFrameIndex = 0;
            } else {
                currentFrameIndex++;
            }
            showFrame(currentFrameIndex);
        }, 1000);
    }
});

// 显示指定帧（核心修正：frameChart → riskTimelineChart）
function showFrame(index) {
    if (frameList.length === 0 || index < 0 || index >= frameList.length) return;

    currentFrameIndex = index;
    const frame = frameList[index];

    // 显示当前帧
    currentFrameImg.src = `data:image/jpeg;base64,${frame.frame_base64}`;
    frameTag.textContent = frame.is_risk ? '违规帧' : '安全帧';
    frameTag.className = `frame-tag ${frame.is_risk ? 'tag-risk' : 'tag-safe'}`;

    frameIndex.textContent = `${index + 1}/${frameList.length}`;
    frameHorror.textContent = frame.horror.toFixed(2) + '%';
    frameViolence.textContent = frame.violence.toFixed(2) + '%';
    frameNsfw.textContent = frame.nsfw.toFixed(3) + '%';
    frameIsRisk.textContent = frame.is_risk ? '违规' : '安全';
    frameIsRisk.className = `stat-value ${frame.is_risk ? 'stat-risk' : 'stat-safe'}`;
    frameSingleDuration.textContent = frame.single_frame_duration ? frame.single_frame_duration.toFixed(4) + ' 秒' : '0.0000 秒';

    // 更新缩略图选中状态
    const thumbnails = document.querySelectorAll('.frame-thumbnail');
    thumbnails.forEach(thumb => {
        thumb.classList.remove('active');
        if (parseInt(thumb.dataset.index) === index) {
            thumb.classList.add('active');
        }
    });

    // 更新按钮状态
    prevFrameBtn.disabled = index === 0;
    nextFrameBtn.disabled = index === frameList.length - 1;

    // 高亮时序图当前帧（修正变量名）
    if (riskTimelineChart) {
        riskTimelineChart.update('none'); // 无动画更新
        // 可选：滚动图表到当前帧位置
        const chartXAxis = riskTimelineChart.scales.x;
        if (chartXAxis) {
            chartXAxis.scroll('center', index + 1, false);
        }
    }
}

// 显示错误
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