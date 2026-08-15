---
name: video-summarize
description: "视频总结（语音+画面+公式三通道）。Use when 用户发本地视频/链接要总结，数学教学视频最佳（公式转LaTeX）。"
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [video, transcription, math, formula, whisper, pix2text]
    related_skills: [youtube-content, office-to-markdown]
---

# 视频总结（三通道）

## When to Use

用户发**本地视频文件路径/链接**要求总结内容，尤其**数学/教学视频**（板书公式多，语音转写覆盖不了公式）。输出：内容总结 + 分章节要点 + 公式LaTeX清单。

## 环境（已就绪，勿重装）

| 组件 | 位置 |
|---|---|
| 脚本目录 | `~/.hermes/scripts/video_summarize/` |
| extract_media.py | ffmpeg提音频(16kHz mono)+scene抽帧(上限40)+时间戳 → meta.json；重跑自动清理旧输出 |
| transcribe.py | faster-whisper **medium**（Hermes venv `~/.hermes/hermes-agent/venv/bin/python`），语言自动检测 |
| formula_extract.py | Pix2Text（独立venv `~/.pix2text-venv/bin/python`，**必须 `env -u PYTHONPATH`**）；含垃圾过滤+全局去重 |
| 模型缓存 | whisper: `~/.cache/huggingface`；pix2text: `~/.pix2text/`（首次自动下载） |

## 工作流（按序执行）

```bash
# ① 预处理（快）
python3 ~/.hermes/scripts/video_summarize/extract_media.py "<视频路径>" <workdir>

# ② 转写（medium首跑下载~1.5GB；3分钟视频约5-10分钟，放后台）
HF_HUB_ENABLE_HF_TRANSFER=1 ~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/video_summarize/transcribe.py <workdir>/audio.wav <workdir>/transcript.txt [model] [language]
# 模型默认medium；language默认None自动检测，可传"zh"/"en"强制

# ③ 公式识别（40帧约2-3分钟，放后台）
env -u PYTHONPATH ~/.pix2text-venv/bin/python ~/.hermes/scripts/video_summarize/formula_extract.py <workdir>/meta.json

# ④ 画面理解（agent用vision_analyze逐帧看，每张~18s）
# 策略：只看首帧+每10帧取1张+formulas.json含公式的帧，≤5张

# ⑤ 融合总结（读 transcript.txt + formulas.json + vision结果 → 输出）
# 输出文件建议存 ~/Documents/video_summaries/（/tmp重启即失）
```

## 输出模板

```
📐 视频总结：《主题》
⏱ 时长 / 📁 来源

📚 内容概要（3-5句）

📖 分章节要点（时间戳）
[00:00-01:20] 章节名
- 要点...

📐 公式清单（LaTeX，可复制）
1. 求根公式: x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}   ← @01:23
2. ...

⚠️ 难点/易错点提示
```

## 坑（已踩，务必遵守）

1. **Pix2Text v1.1 返回格式**：无内容→空字符串 `""`；有公式→**字符串**含 `$$...$$\n$$...$$` 块（不是dict列表）；混合文本可能dict。formula_extract.py 已做三类兼容解析，勿改。
2. **PYTHONPATH污染**：Pix2Text必须 `env -u PYTHONPATH` + pix2text venv python，否则import错乱（同MinerU方案）。
3. **独立venv**：Pix2Text在`~/.pix2text-venv`（uv建，Python 3.11），与Hermes venv隔离。faster-whisper在Hermes venv。
4. **scene抽帧0帧**：静态画面视频会fallback按秒抽帧（extract_media.py已处理）。
5. **公式去重与过滤（2026-08-12新增）**：formula_extract.py 内置 `is_garbage()` 保守过滤（\alpha\alpha/\min\times/N U^{2}等明显垃圾、\begin>\end不平衡、过短） + `normalize_formula()` 全局去重（保留首次出现含时间戳）。真实案例 42→25。
6. **国内下载whisper模型加速（重要）**：HF直连慢（large-v3 18分钟只下579M）。**先装 `pip install hf_transfer`，再 `HF_HUB_ENABLE_HF_TRANSFER=1` 运行**（多线程加速，medium 1.5GB 几分钟下完）。hf-mirror.com 会 308 重定向回原站（无效）；ModelScope 无该模型镜像。中文优先 medium（large-v3 太大慢），精度足够。
7. **链接视频**：需yt-dlp（暂未装），用户习惯先下载，发本地路径即可。
8. **vision模型**：辅助mimo-v2.5，**主模型无视觉时**（如deepseek），vision_analyze自动走辅助模型，正常调用即可。
9. **手写板书公式精度限制**：低分辨率（960x720）下手写推导 LaTeX 有噪点，**题目级公式准确、推导级仅供辅助**——由语音+画面通道补足。建议1080p+视频源。
10. **竖屏视频 CoreML 崩溃（2026-08-12新增）**：Pix2Text 用 CoreML provider，竖屏帧（如544x960）resize 后宽非32倍数 → ONNX Runtime "Error in building plan" 全部帧失败。对策：a) `Pix2Text(..., device="cpu")` 可跑但 36s/张（40帧约24分钟，仅必需时用）；b) **访谈/评论类无公式视频直接跳过公式通道**（Pix2Text 对人物画面误判成公式垃圾，无意义）——先用 vision 看首帧判断视频类型，无板书公式则跳过。横屏数学视频不受影响（32倍数OK）。

## 验证

- 真实视频端到端跑通：3分钟数学教学视频，40帧抽取、语音转写（97段）、极限公式LaTeX提取、vision解题步骤理解全部成功（2026-08-12）。
- 公式识别质量：题目级公式（极限题/e^A-e^B技巧）精确转LaTeX；去重+过滤后 42→25。
- 回归测试（2026-08-12）：修复后关键公式全部保留，3个垃圾正确过滤。
