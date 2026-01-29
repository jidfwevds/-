import os
import cv2
import queue
import threading
import subprocess
import json
import numpy as np
from enum import Enum


class SamplingStrategy(Enum):
    FIXED_COUNT = "fixed_count"  # 数美策略1：固定帧数 (checkFrameCount)
    FIXED_INTERVAL = "fixed_interval"  # 数美策略2：固定频率 (detectFrequency)
    ADVANCED_INTERVAL = "advanced_interval"  # 数美策略3：动态频率 (advancedFrequency)
    CONTENT_AWARE = "content_aware"  # 增强策略：根据内容变化动态采样


# ========== 核心配置 (根据您的需求调整) ==========
# 选择您的抽帧策略：改为 高级动态间隔
SAMPLING_STRATEGY = SamplingStrategy.ADVANCED_INTERVAL

# 策略参数配置
STRATEGY_CONFIG = {
    SamplingStrategy.FIXED_COUNT: {
        'check_frame_count': 30  # 总共抽取多少帧（包含首尾帧）
    },
    SamplingStrategy.FIXED_INTERVAL: {
        'detect_frequency': 5  # 每多少秒抽一帧（单位：秒）
    },
    SamplingStrategy.ADVANCED_INTERVAL: {
        # 数美高级频率配置 (advanced_frequency)
        # 格式: {"durationPoints":[分界点1,分界点2],"frequencies":[频率1,频率2,频率3]}
        # 表示：
        #   时长 ≤ 分界点1(秒): 按 频率1(秒/帧) 抽帧
        #   分界点1 < 时长 ≤ 分界点2: 按 频率2(秒/帧) 抽帧
        #   时长 > 分界点2: 按 频率3(秒/帧) 抽帧
        'advanced_frequency': {
            'duration_points': [30, 300],  # 短视频、中等视频、长视频的分界点（单位：秒）
            'frequencies': [1, 3, 5]       # 对应的抽帧频率（单位：秒/帧）
        }
    },
    SamplingStrategy.CONTENT_AWARE: {
        'base_interval': 2.0,
        'min_interval': 0.5,
        'max_interval': 10.0,
        'change_threshold': 15.0
    }
}
# ========== 配置结束 ==========


class SmartFrameExtractor:
    def __init__(self, video_path, strategy=SAMPLING_STRATEGY, config=None):
        self.video_path = video_path
        self.strategy = strategy
        self.config = config or STRATEGY_CONFIG.get(strategy, {})
        self.video_info = {}

    def get_video_info(self):
        """获取视频信息（复用您的ffprobe逻辑）"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                self.video_path
            ]
            result = subprocess.check_output(cmd, encoding='utf-8')
            info = json.loads(result)
            stream = next(s for s in info['streams'] if s['codec_type'] == 'video')

            fps = eval(stream['avg_frame_rate'])
            total_frames = int(stream['nb_frames']) if 'nb_frames' in stream else 0
            duration = float(info['format']['duration']) if 'duration' in info['format'] else 0
            width = int(stream['width'])
            height = int(stream['height'])

            self.video_info = {
                'fps': fps,
                'total_frames': total_frames,
                'duration': duration,
                'resolution': f"{width}x{height}",
                'width': width,
                'height': height
            }
            return self.video_info

        except Exception as e:
            print(f"⚠️ ffprobe获取视频信息失败，使用OpenCV备选方案：{e}")
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                return None

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            self.video_info = {
                'fps': fps,
                'total_frames': total_frames,
                'duration': duration,
                'resolution': f"{width}x{height}",
                'width': width,
                'height': height
            }
            return self.video_info

    def _get_interval_for_duration(self, duration):
        """
        根据视频时长和配置，确定应该使用的抽帧间隔（秒）。
        完全按照数美 advanced_frequency 逻辑实现。
        """
        # 获取配置，如果配置不存在则使用默认值
        adv_config = self.config.get('advanced_frequency', {})
        duration_points = adv_config.get('duration_points', [30, 300])
        frequencies = adv_config.get('frequencies', [1, 3, 5])

        # 根据时长选择频率
        if duration <= duration_points[0]:
            interval_sec = frequencies[0]  # 短视频，密集抽帧
        elif duration <= duration_points[1]:
            interval_sec = frequencies[1]  # 中等视频，中等抽帧
        else:
            interval_sec = frequencies[2]  # 长视频，稀疏抽帧

        print(f"  时长{duration:.1f}秒 -> 应用间隔: {interval_sec}秒/帧")
        return interval_sec

    def calculate_frame_indices(self):
        """
        根据ADVANCED_INTERVAL策略计算需要抽取的帧索引
        返回：需要抽取的帧索引列表
        """
        fps = self.video_info['fps']
        duration = self.video_info['duration']
        total_frames = self.video_info['total_frames']

        if fps <= 0 or duration <= 0:
            print("⚠️ 无法获取有效的视频信息，退回安全模式")
            return list(range(min(30, total_frames)))

        frame_indices = []

        if self.strategy == SamplingStrategy.ADVANCED_INTERVAL:
            # 1. 根据视频时长，确定抽帧间隔（秒）
            interval_sec = self._get_interval_for_duration(duration)

            # 2. 将间隔（秒）转换为间隔（帧数）
            interval_frames = int(round(interval_sec * fps))
            if interval_frames <= 0:
                interval_frames = int(fps)  # 最低保障：1秒1帧

            # 3. 从视频开始，每隔 interval_frames 抽一帧
            idx = 0
            while idx < total_frames:
                frame_indices.append(idx)
                idx += interval_frames

            # 4. 确保抽取最后一帧（重要）
            if total_frames - 1 not in frame_indices:
                frame_indices.append(total_frames - 1)

        elif self.strategy == SamplingStrategy.FIXED_COUNT:
            n = self.config.get('check_frame_count', 30)
            if n <= 2:
                n = 3
            interval = total_frames / (n - 1)
            for i in range(n):
                idx = int(round(i * interval))
                if idx >= total_frames:
                    idx = total_frames - 1
                frame_indices.append(idx)

        elif self.strategy == SamplingStrategy.FIXED_INTERVAL:
            interval_sec = self.config.get('detect_frequency', 5)
            interval_frames = int(round(interval_sec * fps))
            if interval_frames <= 0:
                interval_frames = int(fps)
            idx = 0
            while idx < total_frames:
                frame_indices.append(idx)
                idx += interval_frames

        elif self.strategy == SamplingStrategy.CONTENT_AWARE:
            base_interval = self.config.get('base_interval', 2.0)
            base_interval_frames = int(round(base_interval * fps))
            idx = 0
            while idx < total_frames:
                frame_indices.append(idx)
                idx += base_interval_frames

        # 去重排序
        frame_indices = sorted(set(frame_indices))
        # 确保不超过总帧数
        frame_indices = [idx for idx in frame_indices if idx < total_frames]

        print(f"📊 策略[{self.strategy.value}]：视频{duration:.1f}秒，共{total_frames}帧，计划抽取{len(frame_indices)}帧")
        return frame_indices

    def extract_frames_by_indices(self, frame_indices, callback):
        """
        根据给定的帧索引抽取帧
        :param frame_indices: 要抽取的帧索引列表
        :param callback: 回调函数，接收(帧数据, 帧索引)
        :return: 实际抽取的帧数
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"❌ 无法打开视频文件：{self.video_path}")
            return 0

        extracted_count = 0
        current_frame = 0
        indices_to_extract = set(frame_indices)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if current_frame in indices_to_extract:
                callback(frame.copy(), current_frame)
                extracted_count += 1

                if extracted_count % 5 == 0:
                    print(f"📸 已抽取{extracted_count}/{len(frame_indices)}帧")

            current_frame += 1

            if extracted_count >= len(frame_indices):
                break

        cap.release()
        return extracted_count


def _safe_put_frame(queue_obj, max_size, frame, idx):
    """安全地将帧放入队列，控制队列大小"""
    while queue_obj.qsize() >= max_size:
        threading.Event().wait(0.1)
    queue_obj.put(('frame_data', frame, idx))


def extract_frames_to_queue(video_path, frame_queue, max_queue_size=50, strategy=SAMPLING_STRATEGY):
    """
    智能抽帧到内存队列（兼容您现有接口）
    这是您的主后端程序调用的唯一函数，接口保持不变。
    """
    def producer():
        try:
            extractor = SmartFrameExtractor(video_path, strategy)

            video_info = extractor.get_video_info()
            if not video_info:
                frame_queue.put(('error', '无法获取视频信息'))
                return

            total_frames = video_info['total_frames']
            fps = video_info['fps']
            duration = video_info['duration']
            resolution = video_info['resolution']

            print(f"📹 视频信息：总帧数{total_frames}，帧率{fps:.2f}，时长{duration:.2f}秒，分辨率{resolution}")
            frame_queue.put(('video_info', total_frames, fps, duration, resolution))

            # 计算帧索引并抽取
            frame_indices = extractor.calculate_frame_indices()
            print(f"📋 计划抽取 {len(frame_indices)} 帧 (原视频 {total_frames} 帧)")

            extracted_count = extractor.extract_frames_by_indices(
                frame_indices,
                lambda frame, idx: _safe_put_frame(frame_queue, max_queue_size, frame, idx)
            )

            frame_queue.put(None)
            print(f"✅ 智能抽帧完成，共抽取{extracted_count}帧到队列")

        except Exception as e:
            error_msg = f'抽帧异常：{str(e)}'
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            frame_queue.put(('error', error_msg))

    producer_thread = threading.Thread(target=producer)
    producer_thread.start()
    return producer_thread


# 兼容原有导入
__all__ = ['extract_frames_to_queue', 'SamplingStrategy']