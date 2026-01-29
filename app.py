import subprocess
import time
import json
import requests
from flask import Flask, request, render_template, jsonify, send_file, Response
import os
import traceback
import uuid
import queue
import torch
import sys
import shutil
import pickle
from flask import send_from_directory
from urllib.parse import unquote
sys.path.append(os.path.dirname(__file__))
from 下载 import (
    identify_platform,
    download_video_by_url,
    ROOT_DOWNLOAD_DIR as CRAWLER_ROOT_DIR,
    create_dir,
    safe_filename
)
from analyze_GLM import GLM_Vision_API, GLM_API_KEY
#from frame_extractor_v2 import extract_frames_to_queue
from smart_frame_extractor import extract_frames_to_queue, SamplingStrategy
from model_inferencer import infer_batch_from_memory
from risk_judger import (
    is_frame_risky,
    calculate_risk_level,
    calculate_risk_score,
    generate_risk_details
)
import numpy as np
import cv2
import base64
from datetime import datetime

# ========== 持久化视频缓存配置 ==========
VIDEO_CACHE_FILE = os.path.join(os.path.dirname(__file__), "video_cache.pkl")
def save_video_cache():
    with open(VIDEO_CACHE_FILE, 'wb') as f:
        pickle.dump(uploaded_videos, f)
def load_video_cache():
    if os.path.exists(VIDEO_CACHE_FILE):
        with open(VIDEO_CACHE_FILE, 'rb') as f:
            return pickle.load(f)
    return {}

# ========== 爬虫配置 ==========
CRAWLER_DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'crawler_downloads')
import 下载
下载.ROOT_DOWNLOAD_DIR = CRAWLER_DOWNLOAD_DIR
create_dir(CRAWLER_DOWNLOAD_DIR)

FFMPEG_PATH = "C:\\Users\\86187\\Desktop\\ffmpeg-7.1-essentials_build\\bin"
os.environ["PATH"] = FFMPEG_PATH + ";" + os.environ["PATH"]
cv2.ocl.setUseOpenCL(False)
cv2.setNumThreads(1)

app = Flask(__name__, template_folder='.', static_folder='static')

# ========== 全局变量 ==========
uploaded_videos = load_video_cache()
device_info = {}
performance_benchmark = {}
_BATCH_SIZE = 8
_HEARTBEAT_INTERVAL = 2.0

# ========== 关键配置 ==========
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True
FEEDBACK_DIR = os.path.join(os.path.dirname(__file__), "feedbacks")
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

def initialize_system():
    global device_info
    device_info = {
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "cuda_devices": [],
        "pytorch_version": torch.__version__,
        "system_info": {
            "platform": os.name,
            "python_version": os.sys.version.split()[0],
            "processor": os.environ.get('PROCESSOR_IDENTIFIER', 'Unknown')
        }
    }
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            device_info["cuda_devices"].append({
                "id": i,
                "name": torch.cuda.get_device_name(i),
                "capability": torch.cuda.get_device_capability(i),
                "total_memory_mb": round(torch.cuda.get_device_properties(i).total_memory / 1024 ** 2, 2)
            })
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    os.makedirs(CRAWLER_DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'static', 'downloaded'), exist_ok=True)

def is_platform_video_url(url: str) -> bool:
    return identify_platform(url) is not None

def is_direct_mp4_url(url: str) -> bool:
    return url.lower().endswith('.mp4') and ('http' in url.lower())

def download_video_from_url(video_url: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    video_id = str(uuid.uuid4())
    if is_platform_video_url(video_url):
        print(f"⬇️ 识别为短视频URL，调用爬虫下载: {video_url}")
        try:
            download_video_by_url(video_url)
        except Exception as e:
            print(f"爬虫调用异常: {str(e)}")
        platform = identify_platform(video_url)
        if not platform:
            raise RuntimeError(f"无法识别URL所属平台: {video_url}")
        platform_dir = os.path.join(CRAWLER_DOWNLOAD_DIR, platform)
        if not os.path.exists(platform_dir):
            raise RuntimeError(f"爬虫平台目录不存在: {platform_dir}")
        video_files = [f for f in os.listdir(platform_dir) if f.lower().endswith('.mp4')]
        if not video_files:
            raise RuntimeError(f"平台目录下未找到视频文件: {platform_dir}")
        video_files.sort(key=lambda x: os.path.getmtime(os.path.join(platform_dir, x)), reverse=True)
        crawler_video_path = os.path.join(platform_dir, video_files[0])
        safe_name = safe_filename(f"{platform}_{video_id}")
        output_path = os.path.join(output_dir, f"{safe_name}.mp4")
        shutil.copy2(crawler_video_path, output_path)
        print(f"✅ 短视频下载完成: {output_path}")
        return output_path
    elif is_direct_mp4_url(video_url):
        print(f"⬇️ 识别为MP4直链，直接下载: {video_url}")
        output_path = os.path.join(output_dir, f"{video_id}.mp4")
        resp = requests.get(video_url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024 * 50:
            raise RuntimeError("MP4直链下载失败，文件不存在或过小")
        print(f"✅ MP4直链下载完成: {output_path}")
        return output_path
    else:
        raise RuntimeError(f"不支持的URL类型: {video_url}")

@app.after_request
def add_header(response):
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-SSE-Ping-Interval'] = '2000'
    return response

# ========== 目录配置 ==========
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
os.makedirs(STATIC_DIR, exist_ok=True, mode=0o777)

# ========== 接口 ==========
@app.route('/describe-frame', methods=['POST'])
def describe_frame():
    try:
        data = request.get_json()
        if not data or 'image_base64' not in data:
            return jsonify({"success": False,"description": "","error": "缺少图片Base64数据"}), 400
        glm_api = GLM_Vision_API(GLM_API_KEY)
        prompt = data.get('prompt',"请详细描述这张图片中的内容，包括人物、场景、动作、氛围等")
        result = glm_api.describe_image_base64(data['image_base64'], prompt)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False,"description": "","error": f"服务器错误: {str(e)}"}), 500

@app.route('/')
def index():
    return render_template('index.html')

def frame_to_base64(frame_array):
    try:
        if frame_array is None or frame_array.size == 0:
            return None
        if frame_array.dtype != np.uint8:
            frame_array = frame_array.astype(np.uint8)
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, 80]
        retval, buffer = cv2.imencode('.jpg', frame_array, encode_param)
        if not retval:
            return None
        base64_str = base64.b64encode(buffer).decode('utf-8')
        return base64_str
    except Exception as e:
        print(f"❌ 帧转Base64失败: {e}")
        return None

def process_batch(batch_cache, batch_indices, batch_arrays, batch_count, total_infer_time, device_info):
    if not batch_cache:
        return [], 0, batch_count, total_infer_time
    print(f"🚀 开始第{batch_count + 1}批次推理，大小: {len(batch_cache)}")
    infer_start = time.time()
    batch_results = infer_batch_from_memory(batch_cache)
    infer_time = time.time() - infer_start
    batch_count += 1
    total_infer_time += infer_time
    frame_results = []
    if batch_results and len(batch_results) == len(batch_cache):
        for i, result in enumerate(batch_results):
            if i >= len(batch_indices):
                continue
            frame_idx = batch_indices[i]
            frame_array = batch_arrays[i]
            horror = float(result.get('horror', 0))
            violence = float(result.get('violence', 0))
            nsfw = float(result.get('nsfw', 0))
            is_risk = bool(is_frame_risky(result))
            performance_data = result.get('performance', {})
            frame_base64 = frame_to_base64(frame_array)
            if frame_base64:
                frame_data = {
                    'frame_base64': frame_base64,
                    'frame_index': frame_idx,
                    'horror': horror,
                    'violence': violence,
                    'nsfw': nsfw,
                    'is_risk': is_risk,
                    'single_frame_duration': performance_data.get('total_infer_time_ms', 0) / 1000,
                    'performance_stats': {
                        'frame_idx': frame_idx,
                        'batch_size': len(batch_cache),
                        'batch_index': batch_count,
                        'preprocess_time_ms': performance_data.get('preprocess_time_ms', 0),
                        'total_infer_time_ms': performance_data.get('total_infer_time_ms', 0),
                        'fps': performance_data.get('fps', 0),
                        'device': device_info['cuda_devices'][0]['name'] if device_info['cuda_available'] else 'CPU',
                        'mode': 'batch'
                    }
                }
                frame_results.append({
                    'data': frame_data,
                    'idx': frame_idx,
                    'scores': {'horror': horror,'violence': violence,'nsfw': nsfw,'is_risk': is_risk,'single_frame_duration': performance_data.get('total_infer_time_ms',0)/1000}
                })
    else:
        print(f"⚠️ 第{batch_count}批次推理结果异常")
    return frame_results, infer_time, batch_count, total_infer_time

def send_heartbeat():
    return f": heartbeat {datetime.now().timestamp()}\n\n"

@app.route('/upload', methods=['POST'])
def upload_video():
    try:
        content_type = request.headers.get('Content-Type', '')
        if content_type.startswith('application/json'):
            data = request.get_json(silent=True) or {}
            video_url = data.get('video_url', '').strip()
            if not video_url:
                return jsonify({'success': False, 'message': '缺少 video_url'})
            video_id = str(uuid.uuid4())
            download_dir = os.path.join(STATIC_DIR, 'downloaded')
            os.makedirs(download_dir, exist_ok=True)
            local_video_path = download_video_from_url(video_url,output_dir=download_dir)
            public_url = f"/static/downloaded/{os.path.basename(local_video_path)}"
            uploaded_videos[video_id] = {
                'source': 'url',
                'video_source': video_url,
                'path': local_video_path,
                'original_name': os.path.basename(local_video_path),
                'url': public_url
            }
            save_video_cache()
            return jsonify({'success': True,'video_id': video_id,'video_url': public_url,'message': '视频已解析完成'})
        elif content_type.startswith('multipart/form-data'):
            if 'video' not in request.files:
                return jsonify({'success': False, 'message': '没有选择视频文件'})
            file = request.files['video']
            if not file or file.filename == '':
                return jsonify({'success': False, 'message': '没有选择视频文件'})
            video_id = str(uuid.uuid4())
            original_filename = file.filename
            safe_filename_str = original_filename.replace('/', '_').replace('\\', '_').replace(':', '_')
            video_filename = f"{video_id}_{safe_filename_str}"
            video_path = os.path.join(STATIC_DIR, video_filename)
            file.save(video_path)
            public_url = f"/static/{video_filename}"
            uploaded_videos[video_id] = {
                'source': 'local',
                'video_source': video_path,
                'path': video_path,
                'original_name': original_filename,
                'url': public_url
            }
            save_video_cache()
            return jsonify({'success': True,'video_id': video_id,'video_url': public_url,'message': '视频上传成功'})
        else:
            return jsonify({'success': False, 'message': '不支持的请求格式'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False,'message': f'上传失败：{str(e)}'})
# ========== 修复：get-video-info 接口（对齐人工审核字段） ==========
@app.route('/get-video-info')
def get_video_info():
    try:
        video_id = request.args.get('video_id')
        if not video_id:
            return jsonify({'success': False, 'message': '缺少video_id参数'})
        if video_id not in uploaded_videos:
            return jsonify({'success': False, 'message': '视频ID不存在'})

        # 核心：获取人工审核结果，对齐存入的字段名
        re_audit_data = uploaded_videos[video_id].get('re_audit_result', {})

        video_info = {
            'video_id': video_id,
            'original_name': uploaded_videos[video_id]['original_name'],
            'url': uploaded_videos[video_id]['url'],
            'source': uploaded_videos[video_id]['source'],
            'analysis_result': uploaded_videos[video_id].get('analysis_result', {}),
            # ========== 修复：字段名与submit_re_audit对齐 ==========
            're_audit_result': {
                'status': re_audit_data.get('status', 'none'),  # 审核状态
                'risk_level': re_audit_data.get('re_audit_level', ''),  # 风险等级
                'desc': re_audit_data.get('re_audit_desc', '暂无人工审核'),  # 审核说明
                'audit_time': re_audit_data.get('re_audit_time', '暂无')  # 审核时间
            }
        }
        return jsonify({'success': True, 'video_info': video_info})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取视频失败：{str(e)}'})


# ========== 保持：submit_re_audit 接口（确保存入字段正确） ==========
@app.route('/submit-re-audit', methods=['POST'])
def submit_re_audit():
    try:
        data = request.get_json()
        feedback_id = data.get("feedback_id")
        re_audit_data = data.get("re_audit_data")
        if not feedback_id or not re_audit_data:
            return jsonify({"success": False, "message": "参数错误"}), 400
        feedback_file = os.path.join(FEEDBACK_DIR, f"{feedback_id}.json")
        if not os.path.exists(feedback_file):
            return jsonify({"success": False, "message": "反馈记录不存在"}), 404
        with open(feedback_file, "r+", encoding="utf-8") as f:
            feedback = json.load(f)
            feedback.update(re_audit_data)
            f.seek(0)
            json.dump(feedback, f, ensure_ascii=False, indent=2)
            f.truncate()

        # ========== 同步人工审核结果到视频缓存 ==========
        video_id = feedback.get('video_id')
        if video_id and video_id in uploaded_videos:
            # 存入的字段名：re_audit_level/re_audit_desc/re_audit_time（与get-video-info对齐）
            uploaded_videos[video_id]['re_audit_result'] = re_audit_data
            save_video_cache()  # 持久化缓存
            print(f"✅ 人工审核结果已同步到视频缓存 (video_id: {video_id})")

        return jsonify({"success": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"审核提交失败：{str(e)}"}), 500

@app.route('/analyze-sse')
def analyze_sse():
    video_id = request.args.get('video_id')
    if not video_id or video_id not in uploaded_videos:
        return Response(json.dumps({'message': '无效的视频ID'}), mimetype='text/event-stream', status=400)

    def generate_sse():
        last_heartbeat = time.time()
        connection_active = True
        error_occurred = False
        try:
            total_start_time = time.time()
            video_info = uploaded_videos[video_id]
            video_path = video_info['path']
            print(f"📌 开始分析视频: {video_path}")
            yield f"event: connection\ndata: {json.dumps({'status': 'connected', 'message': 'SSE连接已建立'}, ensure_ascii=False)}\n\n"
            frame_queue = queue.Queue(maxsize=50)
            producer_thread = extract_frames_to_queue(video_path, frame_queue, max_queue_size=50)
            total_frames = 0
            fps = 0
            duration = 0
            resolution = ""
            video_info_received_once = False
            frame_infer_results = []
            processed_frames = 0
            total_frames_to_process = 0
            batch_cache = []
            batch_indices = []
            batch_arrays = []
            batch_count = 0
            total_infer_time = 0.0
            producer_finished = False
            last_batch_processed = False

            while connection_active and not error_occurred:
                if time.time() - last_heartbeat > _HEARTBEAT_INTERVAL:
                    yield send_heartbeat()
                    last_heartbeat = time.time()
                if producer_finished and frame_queue.empty() and len(batch_cache) == 0 and last_batch_processed:
                    print("✅ 所有帧处理完成")
                    break
                try:
                    try:
                        item = frame_queue.get(timeout=0.5)
                        if item is None:
                            print("📨 收到结束标记，抽帧完成")
                            producer_finished = True
                            if batch_cache:
                                frame_results, infer_time, batch_count, total_infer_time = process_batch(
                                    batch_cache, batch_indices, batch_arrays,batch_count, total_infer_time, device_info)
                                for frame_result in frame_results:
                                    yield f"event: frame\ndata: {json.dumps(frame_result['data'], ensure_ascii=False)}\n\n"
                                    frame_infer_results.append(frame_result['scores'])
                                    yield send_heartbeat()
                                    last_heartbeat = time.time()
                                batch_cache = []
                                batch_indices = []
                                batch_arrays = []
                                last_batch_processed = True
                                if video_info_received_once and total_frames_to_process > 0:
                                    current_processed = len(frame_infer_results)
                                    progress = round((current_processed / total_frames_to_process) * 100, 1)
                                    current_fps = 0
                                    if total_infer_time > 0 and current_processed > 0:
                                        current_fps = current_processed / total_infer_time
                                    infer_progress_data = {
                                        'title': f'批量推理中...（已处理{current_processed}帧，总{total_frames_to_process}帧，批次{batch_count}）',
                                        'current': current_processed,'total': total_frames_to_process,'progress': progress,
                                        'current_fps': round(current_fps, 2),'batch_size': _BATCH_SIZE}
                                    yield f"event: progress\ndata: {json.dumps(infer_progress_data, ensure_ascii=False)}\n\n"
                            else:
                                last_batch_processed = True
                            continue
                        if item[0] == 'video_info':
                            if not video_info_received_once:
                                total_frames, fps, duration, resolution = item[1], item[2], item[3], item[4]
                                total_frames_to_process = total_frames
                                video_info_received_once = True
                                print(f"📹 视频信息：总帧数{total_frames}，帧率{fps}，时长{duration:.2f}秒，分辨率{resolution}")
                                progress_data = {'title': '抽帧中...（边抽边推理）','current': 0,'total': total_frames,'progress': 0.0}
                                yield f"event: progress\ndata: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
                            continue
                        if item[0] == 'error':
                            error_msg = f'抽帧失败：{item[1]}'
                            yield f"event: error\ndata: {json.dumps({'message': error_msg}, ensure_ascii=False)}\n\n"
                            error_occurred = True
                            continue
                        if item[0] == 'frame_data':
                            frame_array, frame_idx = item[1], item[2]
                            batch_cache.append(frame_array)
                            batch_indices.append(frame_idx)
                            batch_arrays.append(frame_array.copy())
                            processed_frames += 1
                    except queue.Empty:
                        if producer_finished and len(batch_cache) == 0 and last_batch_processed:
                            break
                        continue
                    if len(batch_cache) >= _BATCH_SIZE:
                        frame_results, infer_time, batch_count, total_infer_time = process_batch(
                            batch_cache, batch_indices, batch_arrays,batch_count, total_infer_time, device_info)
                        for frame_result in frame_results:
                            yield f"event: frame\ndata: {json.dumps(frame_result['data'], ensure_ascii=False)}\n\n"
                            frame_infer_results.append(frame_result['scores'])
                            yield send_heartbeat()
                            last_heartbeat = time.time()
                        batch_cache = []
                        batch_indices = []
                        batch_arrays = []
                        if video_info_received_once and total_frames_to_process > 0:
                            current_processed = len(frame_infer_results)
                            progress = round((current_processed / total_frames_to_process) * 100, 1)
                            current_fps = 0
                            if total_infer_time > 0 and current_processed > 0:
                                current_fps = current_processed / total_infer_time
                            infer_progress_data = {
                                'title': f'批量推理中...（已处理{current_processed}帧，总{total_frames_to_process}帧，批次{batch_count}）',
                                'current': current_processed,'total': total_frames_to_process,'progress': progress,
                                'current_fps': round(current_fps, 2),'batch_size': _BATCH_SIZE}
                            yield f"event: progress\ndata: {json.dumps(infer_progress_data, ensure_ascii=False)}\n\n"
                except Exception as e:
                    print(f"⚠️ 消费者循环出错：{str(e)}")
                    traceback.print_exc()
                    error_data = {'message': f'处理过程中出错：{str(e)}'}
                    yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    error_occurred = True
                    continue
            if producer_thread and producer_thread.is_alive():
                producer_thread.join(timeout=5.0)
            if error_occurred:
                print("❌ 处理过程中发生错误")
                return
            infer_end_time = time.time()
            infer_duration = round(infer_end_time - total_start_time, 2)
            if not frame_infer_results:
                error_msg = f"没有有效帧完成推理"
                print(f"❌ {error_msg}")
                yield f"event: error\ndata: {json.dumps({'message': error_msg}, ensure_ascii=False)}\n\n"
                return

            horror_scores = [f["horror"] for f in frame_infer_results if "horror" in f]
            violence_scores = [f["violence"] for f in frame_infer_results if "violence" in f]
            nsfw_scores = [f["nsfw"] for f in frame_infer_results if "nsfw" in f]
            risk_frames = sum(1 for f in frame_infer_results if f.get("is_risk", False))
            risk_ratio = risk_frames / len(frame_infer_results) if frame_infer_results else 0
            avg_horror = sum(horror_scores) / len(horror_scores) if horror_scores else 0
            avg_violence = sum(violence_scores) / len(violence_scores) if violence_scores else 0
            avg_nsfw = sum(nsfw_scores) / len(nsfw_scores) if nsfw_scores else 0

            avg_infer_time_per_frame = total_infer_time / len(frame_infer_results) * 1000 if frame_infer_results else 0
            infer_fps = len(frame_infer_results) / total_infer_time if total_infer_time > 0 else 0
            overall_fps = len(frame_infer_results) / infer_duration if infer_duration > 0 else 0
            avg_batch_size = len(frame_infer_results) / batch_count if batch_count > 0 else 0
            batch_efficiency = (avg_batch_size / _BATCH_SIZE * 100) if _BATCH_SIZE > 0 else 0

            risk_level = calculate_risk_level(avg_horror, avg_violence, avg_nsfw, risk_ratio)
            risk_score = calculate_risk_score(avg_horror, avg_violence, avg_nsfw, risk_ratio, risk_level)
            risk_desc = generate_risk_details(avg_horror, avg_violence, avg_nsfw)

            complete_data = {
                'risk_level': risk_level or "未知",'risk_score': float(risk_score) if risk_score is not None else 0.0,
                'risk_desc': risk_desc or "分析完成",'video_resolution': resolution or "未知",
                'video_duration': round(float(duration), 2) if duration else 0.0,'video_fps': round(float(fps), 2) if fps else 0.0,
                'total_frames': int(total_frames) if total_frames else len(frame_infer_results),'analyzed_frames': len(frame_infer_results),
                'risk_frames': int(risk_frames),'risk_ratio': round(float(risk_ratio), 4),
                'avg_horror': round(float(avg_horror), 2),'avg_violence': round(float(avg_violence), 2),
                'avg_nsfw': round(float(avg_nsfw), 3),'video_filename': video_info.get('filename', ''),
                'total_duration': round(float(infer_duration), 2),
                'avg_single_frame_duration': round(float(avg_infer_time_per_frame), 2) / 1000,
                'batch_performance': {
                    'batch_size': _BATCH_SIZE,'total_batches': int(batch_count),'avg_batch_size': round(float(avg_batch_size), 2),
                    'batch_efficiency_percent': round(float(batch_efficiency), 1),
                    'avg_inference_time_per_frame_ms': round(float(avg_infer_time_per_frame), 2),
                    'inference_fps': round(float(infer_fps), 2),'overall_fps': round(float(overall_fps), 2),
                    'total_inference_time_seconds': round(float(total_infer_time), 3),
                    'frames_per_second_overall': round(len(frame_infer_results) / infer_duration,2) if infer_duration > 0 else 0,
                    'inference_mode': 'batch',
                    'device': device_info['cuda_devices'][0]['name'] if device_info['cuda_available'] and device_info['cuda_devices'] else 'CPU'
                },'device_info': device_info
            }
            print("📊 发送分析完成事件...")
            try:
                complete_json = json.dumps(complete_data, ensure_ascii=False)
                # 强制保存分析结果到视频缓存
                uploaded_videos[video_id]['analysis_result'] = complete_data
                save_video_cache()  # 立即持久化
                yield f"event: complete\ndata: {complete_json}\n\n"
            except Exception as e:
                print(f"❌ 发送完成事件失败: {e}")
                traceback.print_exc()
                error_data = {'message': f'发送结果失败：{str(e)}'}
                yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return
            yield f"event: success\ndata: {json.dumps({'status': 'analysis_completed', 'message': '分析成功完成'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            print(f"❌ SSE生成器异常: {str(e)}")
            traceback.print_exc()
            error_data = {'message': f'分析失败：{str(e)}'}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        finally:
            print("🔌 SSE连接关闭")
    return Response(generate_sse(),mimetype='text/event-stream',headers={'Cache-Control': 'no-cache','Connection': 'keep-alive','X-Accel-Buffering': 'no','X-SSE-Ping-Interval': '2000'})

@app.route('/device-info', methods=['GET'])
def get_device_info():
    return jsonify({'success': True,'device_info': device_info,'performance_benchmark': performance_benchmark,'batch_size': _BATCH_SIZE})

@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.get_json()
        if not data or not data.get("feedback_id"):
            return jsonify({"success": False, "message": "参数错误，缺少反馈ID"}),400
        feedback_id = data["feedback_id"]
        feedback_file = os.path.join(FEEDBACK_DIR, f"{feedback_id}.json")
        # 确保目录存在
        os.makedirs(FEEDBACK_DIR, exist_ok=True)
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True, "feedback_id": feedback_id})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"提交失败：{str(e)}"}),500

@app.route('/get-feedback-list', methods=['GET'])
def get_feedback_list():
    try:
        feedbacks = []
        if os.path.exists(FEEDBACK_DIR):
            for filename in os.listdir(FEEDBACK_DIR):
                if filename.endswith(".json"):
                    file_path = os.path.join(FEEDBACK_DIR, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        fb = json.load(f)
                        feedbacks.append(fb)
        feedbacks.sort(key=lambda x: x['feedback_time'], reverse=True)
        return jsonify({"success": True, "feedbacks": feedbacks})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"获取失败：{str(e)}"}),500

@app.route('/get-feedback', methods=['GET'])
def get_feedback():
    try:
        feedback_id = request.args.get('feedback_id')
        if not feedback_id:
            return jsonify({"success": False, "message": "缺少feedback_id参数"}),400
        feedback_file = os.path.join(FEEDBACK_DIR, f"{feedback_id}.json")
        if not os.path.exists(feedback_file):
            return jsonify({"success": False, "message": "反馈记录不存在"}),404
        with open(feedback_file, "r", encoding="utf-8") as f:
            feedback = json.load(f)
        return jsonify({"success": True, "feedback": feedback})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"获取失败：{str(e)}"}),500


@app.route('/get-re-audit-result', methods=['GET'])
def get_re_audit_result():
    try:
        video_id = request.args.get("video_id")
        if not video_id:
            return jsonify({"success": False, "message": "缺少video_id参数"}),400
        if os.path.exists(FEEDBACK_DIR):
            for filename in os.listdir(FEEDBACK_DIR):
                if filename.endswith(".json"):
                    file_path = os.path.join(FEEDBACK_DIR, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        feedback = json.load(f)
                        if feedback.get("video_id") == video_id and feedback.get("status") == "completed":
                            return jsonify({"success": True, "result": feedback})
        return jsonify({"success": False, "message": "暂无审核结果"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"查询失败：{str(e)}"}),500

# 新增：接收前端分析结果并更新缓存
@app.route('/update-video-analysis', methods=['POST'])
def update_video_analysis():
    try:
        data = request.get_json()
        video_id = data.get('video_id')
        analysis_result = data.get('analysis_result')

        # 校验参数
        if not video_id or not analysis_result:
            return jsonify({'success': False, 'message': '缺少video_id或analysis_result参数'})
        if video_id not in uploaded_videos:
            return jsonify({'success': False, 'message': '视频ID不存在'})

        # 更新视频缓存的分析结果
        uploaded_videos[video_id]['analysis_result'] = analysis_result
        save_video_cache()  # 持久化缓存

        return jsonify({'success': True, 'message': '分析结果已同步到后端'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'同步失败：{str(e)}'})

@app.route('/static/<path:filename>')
def serve_static(filename):
    # 直接用Flask内置的send_from_directory，自动处理文件释放，稳定无锁
    return send_from_directory(STATIC_DIR, filename, mimetype='video/mp4')
# ========== 页面路由 ==========
@app.route('/feedback.html')
def feedback_page():
    return render_template('feedback.html')

@app.route('/audit.html')
def audit_page():
    return render_template('audit.html')

if __name__ == '__main__':
    initialize_system()
    print("✅ 启动成功 === 访问地址说明 ===")
    print("✅ 视频分析上传页: http://127.0.0.1:5000")
    print("✅ 人工审核后台: http://127.0.0.1:5000/audit.html")
    print("="*60)
    app.run(host='0.0.0.0',port=5000,debug=False,threaded=True,use_reloader=False,passthrough_errors=True)