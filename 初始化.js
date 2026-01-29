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