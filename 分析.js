function startAnalysisSSE(videoId) {
    console.log('开始SSE分析，videoId:', videoId);
    // =====【局部刷新核心 - 重置所有状态 开始】===== 无全局变量，纯原有变量重置
    frameList = [];
    currentFrameIndex = 0;
    analysisComplete = false;
    currentBatchInfo = "";
    connectionStatus = "connecting";
    isPlaying = false; // 帧播放状态重置
    if (framePlayTimer) clearInterval(framePlayTimer); // 清除帧播放定时器
    timelineSelectedFrameIndex = -1; // 时序图选中帧索引重置
    // 释放视频blob资源 防止内存泄漏
    if (localVideoUrl) { URL.revokeObjectURL(localVideoUrl); localVideoUrl = ''; }
    // =====【局部刷新核心 - 重置所有状态 结束】=====

    // 重置UI - 局部刷新核心UI重置
    hideAllAreas();
    progressArea.style.display = 'block';
    stopAnalysisContainer.style.display = 'block'; // 显示停止分析按钮
    progressFill.style.width = '0%';
    progressText.textContent = '当前进度：0%';
    performanceInfo.textContent = '';
    frameListEl.innerHTML = '';
    destroyAllCharts();
    // 额外UI重置 局部刷新必加
    resultArea.style.display = 'none';
    framePreviewArea.style.display = 'none';
    fullVideoSection.style.display = 'none';
    fullVideoLoading.style.display = 'none';
    fullVideoTip.style.display = 'none';
    document.getElementById('frameDescBubble').style.display = 'none';
    isDescribingFrame = false;
    currentDescFrameIndex = -1;

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

        // ========== 新增：将分析结果同步到后端 ==========
        if (window.currentVideoId) { // 确保video_id已保存（上传/获取视频时赋值）
            fetch('/update-video-analysis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_id: window.currentVideoId,
                    analysis_result: resultData // 把前端的分析结果传给后端
                })
            }).then(res => res.json())
              .then(resp => {
                  resp.success
                      ? console.log('✅ 分析结果已同步到后端')
                      : console.warn('⚠️ 同步分析结果失败:', resp.message);
              }).catch(err => {
                  console.error('❌ 同步请求失败:', err);
              });
        }

        // 绘制所有图表（原代码保留，内部已修改为智能帧逻辑）
        if (frameList.length > 0) {
            renderRiskTimelineChart(resultData);    // 时序风险波动图
            renderRiskCategoryChart(resultData);    // 风险类别雷达图
        } else {
            console.warn('⚠️ 无帧数据，跳所有图表绘制');
        }

        // 更新UI（原代码保留）
        progressFill.style.width = '100%';
        progressTitle.firstElementChild.textContent = '分析完成';
        progressText.textContent = '分析完成！';
        progressStatus.style.display = 'none';

        // 显示结果区域（原代码保留）
        setTimeout(() => {
            progressArea.style.display = 'none';
            stopAnalysisContainer.style.display = 'none';
            resultArea.style.display = 'block';
            framePreviewArea.style.display = 'block';
            startAnalysisBtn.disabled = false;
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
                            startAnalysisBtn.disabled = false; // 局部刷新：错误后重新启用分析按钮
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
            startAnalysisBtn.disabled = false; // 局部刷新：错误后重新启用分析按钮
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

// 加载完整视频 - 核心修改：视频进度同步智能抽取的帧
function loadFullVideo() {
    console.log('开始加载完整视频...');

    // 显示加载中状态
    fullVideoLoading.style.display = 'block';
    fullVideoTip.style.display = 'none';
    fullVideoSection.style.display = 'block';

    // 清除之前的事件监听器 【重要：防止重复绑定导致多次触发】
    fullVideoPlayer.onloadeddata = null;
    fullVideoPlayer.onerror = null;
    fullVideoPlayer.ontimeupdate = null; // 清空旧的进度同步事件

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
        fullVideoTip.textContent = '✅ 完整视频加载完成，支持播放/暂停/进度条/音量控制，拖动进度条自动同步帧！';
        fullVideoTip.style.color = '#27ae60';

        // 确保视频可以播放
        fullVideoPlayer.play().catch(err => {
            console.log('自动播放被阻止，用户需要手动点击播放:', err);
        });
    });

    // 监听视频错误（仅微调提示文案，无逻辑修改）
    fullVideoPlayer.addEventListener('error', function (e) {
        console.error('完整视频加载错误:', fullVideoPlayer.error);
        fullVideoLoading.style.display = 'none';
        // 优化解码错误提示文案（仅修改这行，其余保留）
        fullVideoTip.textContent = '❌ 视频加载失败（解码错误），请确认视频格式为MP4/WEBM且未损坏，或联系管理员';
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

    // =====【核心修改：视频进度变化 → 同步智能抽取的帧】=====
    fullVideoPlayer.addEventListener('timeupdate', function () {
        if (frameList.length === 0 || !riskTimelineChart) return;

        // 获取视频当前时间和真实帧率
        const currentTime = fullVideoPlayer.currentTime;
        const videoFps = resultData?.video_fps || fullVideoPlayer.getVideoPlaybackQuality().fps || 30;

        // 计算当前时间对应的原始帧索引
        const currentOriginalFrame = Math.floor(currentTime * videoFps);

        // 找到最接近当前原始帧的智能抽取帧
        let closestFrameIndex = 0;
        let minDiff = Infinity;

        frameList.forEach((frame, idx) => {
            const frameOriginalIndex = frame.frame_index;
            const diff = Math.abs(frameOriginalIndex - currentOriginalFrame);
            if (diff < minDiff) {
                minDiff = diff;
                closestFrameIndex = idx;
            }
        });

        // 同步显示最接近的智能抽取帧
        if (closestFrameIndex !== currentFrameIndex) {
            showFrame(closestFrameIndex);
            timelineSelectedFrameIndex = closestFrameIndex;
        }
    });

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
        case '极高风险':
            riskColor = '#9b59b6';
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

// 核心修改：时序图使用智能抽取帧的原始索引作为X轴
function renderRiskTimelineChart(resultData) {
    const chartCanvas = document.getElementById('riskTimelineChart');
    // 销毁旧图表
    if (riskTimelineChart) {
        riskTimelineChart.destroy();
    }

    // 保存全局resultData用于视频进度同步
    window.resultData = resultData;

    // 提取智能抽取帧的原始数据
    const frameOriginalIndices = frameList.map(frame => frame.frame_index); // 智能帧的原始索引
    const horrorScores = frameList.map(frame => frame.horror || 0); // 恐怖分值
    const violenceScores = frameList.map(frame => frame.violence || 0); // 暴力分值
    const nsfwScores = frameList.map(frame => frame.nsfw || 0); // NSFW分值
    const riskFlags = frameList.map(frame => frame.is_risk ? 1 : 0); // 违规标记（1=违规，0=安全）
    // 保存视频帧率用于计算时间（从结果数据中获取）
    const videoFps = resultData.video_fps || 30; // 默认30fps

    // 创建图表
    riskTimelineChart = new Chart(chartCanvas, {
        type: 'line',
        data: {
            labels: frameOriginalIndices, // X轴显示智能帧的原始索引
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
               // =====【核心优化：时序图点击帧 跳转到对应视频时间】=====
            onClick: function(event, elements) {
                // 确保有点击到具体元素且视频播放器存在
                if (elements.length > 0 && fullVideoPlayer && frameList.length>0) {
                    // 获取点击的帧索引（图表中索引从0开始，对应frameList的索引）
                    const frameIndex = elements[0].index;
                    const selectedFrame = frameList[frameIndex];
                    // 计算对应视频时间（秒）：智能帧的原始索引 / 帧率
                    const videoTime = selectedFrame.frame_index / videoFps;

                    // 跳转到视频对应位置并暂停 【完善容错】
                    if (!isNaN(videoTime) && fullVideoPlayer.readyState >= 1) {
                        fullVideoPlayer.currentTime = videoTime;
                        fullVideoPlayer.pause();
                        // ✅ 核心新增：同步显示帧预览+高亮缩略图+图表
                        showFrame(frameIndex);
                        // 记录选中帧索引，启用解读按钮
                        timelineSelectedFrameIndex = frameIndex;
                        const analyzeBtn = document.getElementById('analyzeTimelineFrameBtn');
                        analyzeBtn.disabled = false;
                        analyzeBtn.style.opacity = '1';
                        console.log(`已跳转到智能帧 ${selectedFrame.frame_index}，时间: ${videoTime.toFixed(2)}s`);
                    } else {
                        console.warn('视频尚未加载完成，已选中智能帧：', selectedFrame.frame_index);
                        showFrame(frameIndex); // 视频没加载也高亮帧预览
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: '视频原始帧索引', // 修改X轴标题为原始帧索引
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
                            return `原始帧 ${context[0].label}`; // tooltip标题显示原始帧索引
                        }
                    }
                },
                title: {
                    display: true,
                    text: '智能抽取帧风险分值时序波动图', // 修改标题
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

    console.log('✅ 智能帧时序风险波动图绘制完成');
}

// 2. 绘制风险类别雷达图（无修改）
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
    // 初始化气泡关闭按钮
document.getElementById('bubbleCloseBtn').addEventListener('click', () => {
    document.getElementById('frameDescBubble').style.display = 'none';
    isDescribingFrame = false;
    currentDescFrameIndex = -1;
});
// 新增：调用后端解读帧图片
async function describeFrame(frameIndex) {
    // 修复：初始化未定义的变量（避免ReferenceError）
    if (typeof isDescribingFrame === 'undefined') window.isDescribingFrame = false;
    if (typeof currentDescFrameIndex === 'undefined') window.currentDescFrameIndex = -1;

    // 避免重复请求
    if (isDescribingFrame || currentDescFrameIndex === frameIndex) return;

    const bubble = document.getElementById('frameDescBubble');
    const bubbleContent = document.getElementById('bubbleContent');

    // 显示气泡和加载状态
    bubble.style.display = 'block';
    bubbleContent.innerHTML = `
        <div class="loading-spinner small-spinner"></div>
        <p>正在解析帧 ${frameList[frameIndex].frame_index} 内容...</p>
    `;

    isDescribingFrame = true;
    currentDescFrameIndex = frameIndex;

    try {
        // 获取当前帧的Base64数据
        const frame = frameList[frameIndex];
        if (!frame || !frame.frame_base64) {
            throw new Error('帧图片数据不存在');
        }

        // 调用后端接口
        const response = await fetch('/describe-frame', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image_base64: frame.frame_base64,
                prompt: "请详细描述这张图片中的内容，包括人物、场景、动作、氛围等，语言简洁明了"
            }),
            timeout: 30000 // 30秒超时
        });

        const result = await response.json();

        if (result.success && result.description) {
            // 显示成功结果
            bubbleContent.innerHTML = `
                <div class="bubble-success">✅ 解析完成</div>
                <p><strong>帧 ${frame.frame_index} 内容解读：</strong></p>
                <div style="margin-top: 10px; white-space: pre-wrap;">${result.description}</div>
            `;
        } else {
            // 显示错误信息
            bubbleContent.innerHTML = `
                <div class="bubble-error">❌ 解析失败</div>
                <p>${result.error || '未知错误'}</p>
                <button class="btn" style="margin-top: 10px; padding: 5px 10px; font-size: 12px;" onclick="describeFrame(${frameIndex})">
                    重试解析
                </button>
            `;
        }

    } catch (error) {
        // 处理网络错误
        bubbleContent.innerHTML = `
            <div class="bubble-error">❌ 请求失败</div>
            <p>${error.message || '网络异常，请检查连接'}</p>
            <button class="btn" style="margin-top: 10px; padding: 5px 10px; font-size: 12px;" onclick="describeFrame(${frameIndex})">
                重试解析
            </button>
        `;
        console.error('帧解析失败:', error);
    } finally {
        isDescribingFrame = false;
    }
}

// 显示指定帧（优化：显示智能帧的原始索引）
function showFrame(index) {
    if (frameList.length === 0 || index < 0 || index >= frameList.length) return;

    currentFrameIndex = index;
    const frame = frameList[index];

    // 1. 更新帧预览区域的基础信息（显示原始帧索引）
    currentFrameImg.src = `data:image/jpeg;base64,${frame.frame_base64}`;
    frameTag.textContent = frame.is_risk ? '违规帧' : '安全帧';
    frameTag.className = `frame-tag ${frame.is_risk ? 'tag-risk' : ''}`;
    frameIndex.textContent = `${frame.frame_index} (${index + 1}/${frameList.length})`; // 显示原始索引+顺序索引
    frameHorror.textContent = frame.horror.toFixed(2) + '%';
    frameViolence.textContent = frame.violence.toFixed(2) + '%';
    frameNsfw.textContent = frame.nsfw.toFixed(3) + '%';
    frameIsRisk.textContent = frame.is_risk ? '违规' : '安全';
    frameIsRisk.className = `stat-value ${frame.is_risk ? 'stat-risk' : 'stat-safe'}`;
    frameSingleDuration.textContent = frame.single_frame_duration ? frame.single_frame_duration.toFixed(4) + ' 秒' : '0.0000 秒';

    // 2. 更新缩略图选中状态
    const thumbnails = document.querySelectorAll('.frame-thumbnail');
    thumbnails.forEach(thumb => {
        thumb.classList.remove('active');
        if (parseInt(thumb.dataset.index) === index) {
            thumb.classList.add('active');
        }
    });

    // 3. 禁用/启用帧控制按钮
    prevFrameBtn.disabled = index === 0;
    nextFrameBtn.disabled = index === frameList.length - 1;

    // 4. 仅高亮时序图当前帧（不修改任何范围）
    if (riskTimelineChart) {
        riskTimelineChart.update('none'); // 无动画更新，仅高亮，范围不变
    }
}
// 绑定“解读当前选中帧”按钮点击事件
document.addEventListener('DOMContentLoaded', function() {
    const analyzeBtn = document.getElementById('analyzeTimelineFrameBtn');
    // 初始化按钮样式（禁用状态下透明，可选）
    analyzeBtn.style.opacity = '0.6';
    analyzeBtn.addEventListener('click', function() {
        // 校验：是否已选中时序图帧
        if (timelineSelectedFrameIndex === -1 || frameList.length === 0) {
            alert('请先点击时序图上的帧，选中后再解读！');
            return;
        }

        // 调用原有解读逻辑，传入时序图选中的帧索引
        describeFrame(timelineSelectedFrameIndex);
        console.log(`手动触发：解读时序图选中的智能帧 ${frameList[timelineSelectedFrameIndex].frame_index}`);
    });

    // =====【核心新增：局部刷新 - 停止分析按钮绑定】=====
    const stopBtn = document.getElementById('stopAnalysisBtn');
    if(stopBtn){
        stopBtn.addEventListener('click', function(){
            // 1. 关闭SSE连接
            if(currentSSE){ currentSSE.close(); currentSSE = null; }
            // 2. 清除定时器
            if(framePlayTimer) clearInterval(framePlayTimer);
            // 3. 重置所有状态（局部刷新核心）
            frameList = [];
            currentFrameIndex = 0;
            analysisComplete = false;
            connectionStatus = "stopped";
            isPlaying = false;
            timelineSelectedFrameIndex = -1;
            // 4. 重置UI
            hideAllAreas();
            progressArea.style.display = 'none';
            stopAnalysisContainer.style.display = 'none';
            resultArea.style.display = 'none';
            framePreviewArea.style.display = 'none';
            fullVideoSection.style.display = 'none';
            frameListEl.innerHTML = '';
            performanceInfo.textContent = '';
            destroyAllCharts();
            // 5. 释放资源
            if(localVideoUrl) URL.revokeObjectURL(localVideoUrl);
            // 6. 启用分析按钮
            startAnalysisBtn.disabled = false;
            console.log('✅ 已停止分析，局部刷新完成');
        });
    }
});