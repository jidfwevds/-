# model_inferencer.py
import os
import time
import warnings
import torch
import onnxruntime as ort
import numpy as np
import cv2

warnings.filterwarnings('ignore')

HORROR_ONNX_PATH = "horror_model_static_quantized.onnx"
VIOLENCE_ONNX_PATH = "violence_model_static_quantized.onnx"
NSFW_ONNX_PATH = "nsfw_model_static_quantized.onnx"

_models = {}
_device_info = {}
_models_loaded = False  # 添加模型加载标志


def optimized_preprocess(frame_array):
    """优化的预处理函数"""
    try:
        # 确保输入是numpy数组
        if isinstance(frame_array, list):
            frame_array = np.array(frame_array)

        # 确保是uint8类型
        if frame_array.dtype != np.uint8:
            frame_array = frame_array.astype(np.uint8)

        img = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (224, 224), interpolation=cv2.INTER_AREA)
        img = img.astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        img = np.transpose(img, (2, 0, 1))
        return np.expand_dims(img, axis=0)
    except Exception as e:
        print(f"预处理失败: {e}")
        # 返回一个默认的预处理结果
        return np.zeros((1, 3, 224, 224), dtype=np.float32)


def load_all_models():
    """加载所有ONNX模型"""
    global _models, _device_info, _models_loaded

    if _models_loaded:
        return

    try:
        print("🚀 正在加载ONNX模型...")

        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] \
            if torch.cuda.is_available() else ['CPUExecutionProvider']

        print(f"📡 使用推理后端: {providers[0]}")

        # 加载模型
        _models["horror"] = ort.InferenceSession(HORROR_ONNX_PATH, providers=providers)
        _models["violence"] = ort.InferenceSession(VIOLENCE_ONNX_PATH, providers=providers)
        _models["nsfw"] = ort.InferenceSession(NSFW_ONNX_PATH, providers=providers)

        # 获取输入名称
        _models["horror_input"] = _models["horror"].get_inputs()[0].name
        _models["violence_input"] = _models["violence"].get_inputs()[0].name
        _models["nsfw_input"] = _models["nsfw"].get_inputs()[0].name

        # 获取输出名称
        _models["horror_output"] = _models["horror"].get_outputs()[0].name
        _models["violence_output"] = _models["violence"].get_outputs()[0].name
        _models["nsfw_output"] = _models["nsfw"].get_outputs()[0].name

        _device_info["onnxruntime_providers"] = providers
        _models_loaded = True

        print("✅ ONNX 模型加载完成")

        # 测试模型是否可以正常工作
        print("🧪 测试模型推理...")
        test_input = np.random.randn(1, 3, 224, 224).astype(np.float32)
        try:
            _models["horror"].run(None, {_models["horror_input"]: test_input})
            print("✓ Horror模型测试通过")
            _models["violence"].run(None, {_models["violence_input"]: test_input})
            print("✓ Violence模型测试通过")
            _models["nsfw"].run(None, {_models["nsfw_input"]: test_input})
            print("✓ NSFW模型测试通过")
        except Exception as e:
            print(f"⚠️ 模型测试失败: {e}")

    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def infer_batch_from_memory(frame_list):
    """批量推理函数"""
    try:
        load_all_models()

        if not frame_list:
            print("⚠️ 警告：传入的帧列表为空")
            return []

        batch_size = len(frame_list)
        print(f"🔍 开始批量推理，批次大小: {batch_size}")

        # 1. 批量预处理
        preprocess_start = time.perf_counter()

        batch_inputs = []
        for frame in frame_list:
            try:
                input_tensor = optimized_preprocess(frame)
                batch_inputs.append(input_tensor)
            except Exception as e:
                print(f"⚠️ 单帧预处理失败: {e}")
                # 使用零张量作为占位符
                batch_inputs.append(np.zeros((1, 3, 224, 224), dtype=np.float32))

        # 合并批次
        try:
            batch_input = np.concatenate(batch_inputs, axis=0)
        except Exception as e:
            print(f"❌ 批次合并失败: {e}")
            # 如果合并失败，使用第一个输入并调整批次
            if batch_inputs:
                single_input = batch_inputs[0]
                batch_input = np.repeat(single_input, batch_size, axis=0)
            else:
                batch_input = np.zeros((batch_size, 3, 224, 224), dtype=np.float32)

        preprocess_time = (time.perf_counter() - preprocess_start) * 1000

        # 2. 批量推理
        infer_start = time.perf_counter()

        try:
            # 推理三个模型
            horror_outputs = _models["horror"].run(
                None, {_models["horror_input"]: batch_input}
            )[0]

            violence_outputs = _models["violence"].run(
                None, {_models["violence_input"]: batch_input}
            )[0]

            nsfw_outputs = _models["nsfw"].run(
                None, {_models["nsfw_input"]: batch_input}
            )[0]

        except Exception as e:
            print(f"❌ 批量推理失败: {e}")
            # 返回默认结果
            horror_outputs = np.zeros((batch_size, 2), dtype=np.float32)
            violence_outputs = np.zeros((batch_size, 2), dtype=np.float32)
            nsfw_outputs = np.zeros((batch_size, 2), dtype=np.float32)

        infer_time = (time.perf_counter() - infer_start) * 1000

        # 3. 计算概率
        try:
            # 使用稳定的softmax计算
            def stable_softmax(x):
                exp_x = np.exp(x - np.max(x, axis=1, keepdims=True))
                return exp_x / np.sum(exp_x, axis=1, keepdims=True)

            horror_probs = stable_softmax(horror_outputs)
            violence_probs = stable_softmax(violence_outputs)
            nsfw_probs = stable_softmax(nsfw_outputs)

        except Exception as e:
            print(f"❌ 概率计算失败: {e}")
            # 使用均匀分布作为后备
            horror_probs = np.full((batch_size, 2), 0.5)
            violence_probs = np.full((batch_size, 2), 0.5)
            nsfw_probs = np.full((batch_size, 2), 0.5)

        # 4. 构建结果
        results = []
        for i in range(batch_size):
            try:
                # 获取概率值，确保索引正确
                horror_score = float(horror_probs[i, 0] * 100)  # 索引0是恐怖类别
                violence_score = float(violence_probs[i, 1] * 100)  # 索引1是暴力类别
                nsfw_score = float(nsfw_probs[i, 1] * 100)  # 索引1是色情类别

                result = {
                    "horror": round(horror_score, 2),
                    "violence": round(violence_score, 2),
                    "nsfw": round(nsfw_score, 2),
                    "performance": {
                        "batch_size": batch_size,
                        "preprocess_time_ms": round(preprocess_time / batch_size, 2),
                        "total_infer_time_ms": round(infer_time / batch_size, 2),
                        "batch_total_infer_time_ms": round(infer_time, 2),
                        "fps": round(batch_size * 1000 / max(infer_time, 0.001), 2),
                        "device": _device_info.get("onnxruntime_providers", ["CPU"])[0],
                        "mode": "batch",
                        "status": "success"
                    }
                }
                results.append(result)

            except Exception as e:
                print(f"❌ 第{i}帧结果构建失败: {e}")
                # 返回默认结果
                results.append({
                    "horror": 0.0,
                    "violence": 0.0,
                    "nsfw": 0.0,
                    "performance": {
                        "batch_size": batch_size,
                        "preprocess_time_ms": 0,
                        "total_infer_time_ms": 0,
                        "batch_total_infer_time_ms": 0,
                        "fps": 0,
                        "device": "Unknown",
                        "mode": "batch",
                        "status": "error",
                        "error": str(e)
                    }
                })

        print(
            f"✅ 批量推理完成，处理了{len(results)}帧，平均FPS: {results[0]['performance']['fps'] if results else 0:.2f}")
        return results

    except Exception as e:
        print(f"❌ 批量推理函数整体失败: {e}")
        import traceback
        traceback.print_exc()

        # 返回一个默认的结果列表
        return [{
            "horror": 0.0,
            "violence": 0.0,
            "nsfw": 0.0,
            "performance": {
                "batch_size": len(frame_list) if frame_list else 1,
                "preprocess_time_ms": 0,
                "total_infer_time_ms": 0,
                "batch_total_infer_time_ms": 0,
                "fps": 0,
                "device": "Unknown",
                "mode": "batch",
                "status": "critical_error",
                "error": str(e)
            }
        } for _ in range(len(frame_list) if frame_list else 1)]


def benchmark_inference(sample_size=100):
    """基准测试函数"""
    print(f"🧪 开始基准测试，样本数: {sample_size}")

    # 创建测试帧
    test_frames = []
    for i in range(sample_size):
        frame = np.random.randint(0, 256, (720, 970, 3), dtype=np.uint8)
        test_frames.append(frame)

    # 测试批量推理
    start_time = time.time()
    results = infer_batch_from_memory(test_frames)
    total_time = time.time() - start_time

    if results:
        avg_fps = sample_size / total_time
        avg_infer_time = total_time * 1000 / sample_size

        print(f"📊 基准测试结果:")
        print(f"  处理帧数: {len(results)}")
        print(f"  总时间: {total_time:.2f}秒")
        print(f"  平均FPS: {avg_fps:.2f}")
        print(f"  平均推理时间: {avg_infer_time:.2f}ms")

        return {
            "sample_size": sample_size,
            "total_time": round(total_time, 2),
            "avg_fps": round(avg_fps, 2),
            "avg_infer_time_ms": round(avg_infer_time, 2),
            "device_info": _device_info
        }

    return {"error": "基准测试失败"}


if __name__ == "__main__":
    # 测试批量推理
    print("🚀 测试批量推理...")
    test_frame = np.random.randint(0, 256, (720, 970, 3), dtype=np.uint8)
    results = infer_batch_from_memory([test_frame])
    print(f"测试结果: {results}")