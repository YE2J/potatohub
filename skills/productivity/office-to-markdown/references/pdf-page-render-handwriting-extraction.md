# PDF 页面级手写内容提取（2026-08-17 实测）

## 问题

`pymupdf page.get_images()` 只提取**嵌入位图**（xref 图片对象）。
数学讲义/教辅 PDF 常为「印刷框架 + 手写推导」，**手写内容以页面级渲染
（drawing/扫描底图）存在，不在嵌入图里**——只做嵌入图提取会漏掉全书核心内容。

实测案例：《初高中方程运算表》102 页 PDF
- 文本层仅 13,606 字符（102 页，极稀疏）
- `get_images()` 提取 131 张：99 张是每页重复水印图（md5 相同），仅 31 张有效嵌入图
- 实际 **59 页「文本少」页面全部有内容**（非白占比 1.7%–13.7%），其中约 55 页是手写推导
- 初版分析只做了嵌入图 → 漏掉全部手写核心内容 → 用户两次纠正才暴露

## 判定信号（任一命中 → 必须走全页渲染）

1. **文本层总字符数 << 页数 × 100**（102 页仅 1.3 万字符极可疑）
2. 存在大量「文本 <80 字符」的页面（本案例 59 页）
3. 用户提示「某页是手写/图片/手写内容」

## 检测：像素级判断页面是否有内容（0 token）

不要凭文本少就判「空白页」。渲染后统计非白像素占比：

```python
import pymupdf, numpy as np
doc = pymupdf.open(pdf_path)
for i, page in enumerate(doc):
    t = page.get_text().strip()
    if len(t) >= 80:
        continue
    pix = page.get_pixmap(matrix=pymupdf.Matrix(1.0, 1.0))
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    nonwhite = (arr[:, :, :3].min(axis=2) < 240).mean()
    verdict = '有内容' if nonwhite > 0.01 else '空白'
    print(f'p{i+1:3d} | {len(t):4d} | {nonwhite*100:6.2f}% | {verdict}')
```

判定标准：非白占比 > 1% → 有内容。实测全 102 页**无真正空白页**，
59 页「文本少」页面全部有内容（手写为主）。

## 全页渲染 + 批量 vision 分析（标准路径）

```python
import pymupdf
doc = pymupdf.open(pdf_path)
for i, page in enumerate(doc):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0))  # 2x 足够清晰，102页约11MB
    pix.save(f'/tmp/pages/p{i+1:03d}.png')
```

- 渲染页**已包含嵌入图内容** → 分析渲染页即可，**无需再单独分析嵌入图**
  （省约一半 vision 调用；嵌入图仅作局部放大复核用）
- 逐页 `vision_analyze`（4 张/批并行 + checkpoint 即时落盘，见 SKILL.md 步骤 3）
- 手写识别保留公式结构（分式/根号/上下标）；潦草数字/符号标「⚠️ 建议人工复核」

## 为什么不用 OCR（用户确认 2026-08-17）

| 维度 | 视觉模型 (vision_analyze) | 传统 OCR (Tesseract/PaddleOCR/MinerU) |
|---|---|---|
| 公式结构 | ✅ 保持（分式、根号、上下标） | ❌ 丢失，只出文字流 |
| 手写体 | ✅ 清晰笔迹可读 | 通常较差 |
| 印刷文字 | ✅ | ✅ |
| 适合场景 | 数学公式为主的手写笔记 | 纯文字扫描件 |

数学内容为主 → 视觉模型；纯文字扫描 → OCR。
