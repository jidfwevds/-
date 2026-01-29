# ===================== 风险判定规则配置（基于科学框架） =====================
RISK_CONFIG = {
    # --- 注意：category_weights 已不再用于严重度计算，仅作保留或它用 ---
    "category_weights": {
        "horror": 0.333,
        "violence": 0.333,
        "nsfw": 0.334
    },
    # --- 科学依据：风险矩阵的维度与等级映射 ---
    # 在 RISK_CONFIG 中，将风险矩阵修改为5级
    "risk_matrix_config": {
    # 严重度等级阈值可以微调以匹配新层级
       "severity_levels": [30.0, 60.0, 85.0],  # 低: <25, 中: 25-60, 高: 60-85, 极高: >85
       "occurrence_levels": [0.3, 0.6, 0.85],   # 低: <0.2, 中: 0.2-0.5, 高: 0.5-0.8, 极高: >0.8
    # 索引变为: 0=低, 1=中, 2=高, 3=极高
        "level_matrix": [
        ["低风险", "低风险", "中风险", "中风险"],
        ["低风险", "中风险", "高风险", "高风险"],  # [1][2] 对应 “中高风险”
        ["中风险", "高风险", "高风险", "极高风险"],
        ["中风险", "高风险", "极高风险", "极高风险"]
        ]
    },
    # --- 科学依据：RPN分数计算与映射参数 ---
    "scoring_config": {
        "detection_difficulty": 1.0,
        "rpn_scale_factor": 10.0
    },
    # --- 动态加权参数 (新增) ---
    "dynamic_weighting": {
        "power": 2  # 用于动态计算权重的幂次。e.g., 2表示使用平方。增大此值会进一步放大高风险的权重。
    }
}


# ===================== 核心工具函数：动态权重计算 =====================
def _calculate_dynamic_weights(horror, violence, nsfw):
    """
    根据当前值动态计算三类风险的权重。
    原理：值越高的类别，权重越大。通过乘方(power)操作实现非线性放大。
    """
    power = RISK_CONFIG["dynamic_weighting"]["power"]
    # 计算各值的乘方（防止负值）
    horror_pow = max(horror, 0) ** power
    violence_pow = max(violence, 0) ** power
    nsfw_pow = max(nsfw, 0) ** power
    total_pow = horror_pow + violence_pow + nsfw_pow
    # 避免除以零
    if total_pow <= 0:
        return 1.0 / 3, 1.0 / 3, 1.0 / 3
    # 归一化得到动态权重
    w_h = horror_pow / total_pow
    w_v = violence_pow / total_pow
    w_n = nsfw_pow / total_pow
    return w_h, w_v, w_n


# ===================== 单帧风险判定（基于动态加权强度） =====================
def is_frame_risky(frame_scores):
    """
    判定单帧是否为风险帧（基于动态加权综合强度）
    科学依据：突出主风险的加权平均。
    """
    h = frame_scores.get("horror", 0.0)
    v = frame_scores.get("violence", 0.0)
    n = frame_scores.get("nsfw", 0.0)

    # 1. 计算本帧的动态权重
    w_h, w_v, w_n = _calculate_dynamic_weights(h, v, n)
    # 2. 计算动态加权综合强度
    dynamic_intensity = h * w_h + v * w_v + n * w_n
    # 3. 判定 (阈值可调，此处设为50)
    return dynamic_intensity > 50.0


# ===================== 视频整体风险等级判定（基于风险矩阵） =====================
def calculate_risk_level(avg_horror, avg_violence, avg_nsfw, risk_ratio):
    """
    判定视频整体风险等级
    严重度(S) 使用动态加权平均值。
    """
    # 1. 计算严重度(S) - 【核心修改】使用动态加权平均
    # 先计算整体（平均后）的动态权重
    w_h, w_v, w_n = _calculate_dynamic_weights(avg_horror, avg_violence, avg_nsfw)
    severity = avg_horror * w_h + avg_violence * w_v + avg_nsfw * w_n

    # 2. 发生度(O) = 风险帧比例
    occurrence = risk_ratio

    # 3. & 4. 确定等级索引 (逻辑不变)
    sev_levels = RISK_CONFIG["risk_matrix_config"]["severity_levels"]
    if severity < sev_levels[0]:
        sev_index = 0
    elif severity < sev_levels[1]:
        sev_index = 1
    else:
        sev_index = 2

    occ_levels = RISK_CONFIG["risk_matrix_config"]["occurrence_levels"]
    if occurrence < occ_levels[0]:
        occ_index = 0
    elif occurrence < occ_levels[1]:
        occ_index = 1
    else:
        occ_index = 2

    # 5. 从风险矩阵查询最终等级
    level_matrix = RISK_CONFIG["risk_matrix_config"]["level_matrix"]
    return level_matrix[sev_index][occ_index]


# ===================== 风险分数计算（基于RPN公式） =====================
def calculate_risk_score(avg_horror, avg_violence, avg_nsfw, risk_ratio, risk_level):
    """
    计算风险分数（0-10分）（科学依据：RPN = S × O × D）
    S 使用与等级判定中一致的动态加权严重度。
    """
    # 1. 计算严重度(S) - 与等级判定中的计算完全一致
    w_h, w_v, w_n = _calculate_dynamic_weights(avg_horror, avg_violence, avg_nsfw)
    severity = (avg_horror * w_h + avg_violence * w_v + avg_nsfw * w_n) / 100.0  # 归一化到0-1

    # 2. 发生度(O) = 风险帧比例
    occurrence = risk_ratio

    # 3. 探测度(D)
    detection = RISK_CONFIG["scoring_config"]["detection_difficulty"]

    # 4. 计算原始RPN值
    rpn_raw = severity * occurrence * detection

    # 5. 线性映射到0-10分制
    scale_factor = RISK_CONFIG["scoring_config"]["rpn_scale_factor"]
    score = rpn_raw * scale_factor

    # 6. 确保分数在0-10范围内并保留一位小数
    return round(min(max(score, 0.0), 10.0), 1)

# ===================== 风险说明生成（修正版） =====================
def generate_risk_details(avg_horror, avg_violence, avg_nsfw):
    """
    生成风险说明文本，反映动态加权的效果。
    【修正点】：使风险描述的逻辑与风险等级判定的逻辑完全一致。
    """
    # 计算动态加权严重度及权重（此部分不变）
    w_h, w_v, w_n = _calculate_dynamic_weights(avg_horror, avg_violence, avg_nsfw)
    composite_severity = avg_horror * w_h + avg_violence * w_v + avg_nsfw * w_n

    sev_levels = RISK_CONFIG["risk_matrix_config"]["severity_levels"]

    # 根据严重度级别生成描述和中文处置建议
    if composite_severity >= sev_levels[2]:  # 极高严重度
        details = f"内容安全风险极高，综合严重度{composite_severity:.1f}% 处置建议：拦截告警"

    elif composite_severity >= sev_levels[1]:  # 高严重度
        # 找出主导风险类别
        dominant_risk = ""
        if w_h >= max(w_v, w_n):
            dominant_risk = f"恐怖({avg_horror:.1f}%)"
        elif w_v >= max(w_h, w_n):
            dominant_risk = f"暴力({avg_violence:.1f}%)"
        else:
            dominant_risk = f"色情({avg_nsfw:.1f}%)"
        details = f"风险程度高，综合严重度{composite_severity:.1f}% 处置建议：拦截代答"
    elif composite_severity >= sev_levels[0]:  # 中严重度
        details = f"处置建议：标记限流"
    else:  # 低严重度
        details = f"处置建议：仅记录"  # 中文action

    # 同时返回说明和处置动作
    return details

# ===================== 结果汇总函数（保持不变，但内部逻辑已更新） =====================
def summarize_frames_results(frame_results):
    """
    汇总所有帧的判定结果（适配前端格式）
    :param frame_results: infer_single_frame返回的列表（含is_risk）
    """
    # 提取原始分数
    horror_scores = [f["horror"] for f in frame_results]
    violence_scores = [f["violence"] for f in frame_results]
    nsfw_scores = [f["nsfw"] for f in frame_results]

    # 计算风险帧比例 (调用更新后的 is_frame_risky)
    risk_frames = sum(1 for f in frame_results if f["is_risk"])
    risk_ratio = risk_frames / len(frame_results) if frame_results else 0

    # 计算平均值
    avg_horror = sum(horror_scores) / len(horror_scores) if horror_scores else 0
    avg_violence = sum(violence_scores) / len(violence_scores) if violence_scores else 0
    avg_nsfw = sum(nsfw_scores) / len(nsfw_scores) if nsfw_scores else 0

    # 调用判定函数
    risk_level = calculate_risk_level(avg_horror, avg_violence, avg_nsfw, risk_ratio)
    risk_score = calculate_risk_score(avg_horror, avg_violence, avg_nsfw, risk_ratio, risk_level)
    risk_details = generate_risk_details(avg_horror, avg_violence, avg_nsfw)

    # 返回适配前端的结果
    return {
        "overall_risk": {
            "risk_level": risk_level,
            "score": risk_score,
            "details": risk_details,
            "statistics": {
                "risk_frames": risk_frames,
                "risk_ratio": risk_ratio,
                "avg_horror": avg_horror,
                "avg_violence": avg_violence,
                "avg_porn_risk": avg_nsfw / 100,
                "max_porn_risk": max(nsfw_scores) / 100 if nsfw_scores else 0,
                "max_horror": max(horror_scores) if horror_scores else 0,
                "max_violence": max(violence_scores) if violence_scores else 0
            }
        },
        "frame_results": frame_results,
        "analyzed_frames": len(frame_results)
    }