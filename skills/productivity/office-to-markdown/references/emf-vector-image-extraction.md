# EMF/WMF 矢量图处理与坏图验证 (2026-08 实测)

docx 内嵌图片不只有 PNG/JPG。Word/Visio 绘制的架构图常以 `word/media/imageN.emf`
(WMF/EMF+) 存储。这类矢量图多数工具链无法渲染，但**图中文字可经二进制扫描恢复**。

## 场景判定

- `unzip -o doc.docx word/media/` 后出现 `.emf` / `.wmf` → 矢量图
- PIL 打开报 `cannot identify image file`；pymupdf 报 `FileDataError`；sips 转换失败

## 工具链实测 (macOS, 2026-08) — 均不可渲染 EMF

| 工具 | 结果 |
|---|---|
| `qlmanage -t` | **卡死**（必须 background + timeout + kill；等 90s+ 仍无输出） |
| `sips -s format png` | 失败 |
| Swift NSImage(contentsOfFile:) | `NSImage 无法加载 EMF` |
| pymupdf.open(.emf) | `FileDataError: Failed to open file ... as type emf` |
| PIL | 不支持 |
| LibreOffice/ImageMagick/Inkscape | 未安装（可 `brew install libreoffice` 后 unoconv 转换，属可选升级） |

**结论：不要花时间试渲染；直接走文本提取。**

## 可用方案：UTF-16LE 二进制扫描（网络拓扑/架构图实测成功）

EMF 内嵌文本（节点名/标签）以 UTF-16LE 明文存储（字体段可读，正文段 GDI+ 压缩）。
用关键词过滤可提取全部节点：

```python
import re
with open("image2.emf", "rb") as f:
    data = f.read()
# 领域关键词——按文档主题调整（本案例为网络拓扑）
keywords = ['交换机','网络','办公','核心','汇聚','接入','机房','设备','服务器',
            '防火墙','路由','管理','数据','监控','出口','互联网','专线','安全',
            '无线','AP','终端','云','外网']
found = []
i = 0
while i < len(data) - 4:
    c = data[i] | (data[i+1] << 8)
    if 0x4e00 <= c <= 0x9fff:          # CJK 起始
        j = i; chars = []
        while j < len(data) - 1:
            cc = data[j] | (data[j+1] << 8)
            if (0x4e00 <= cc <= 0x9fff) or (0x3000 <= cc <= 0x303f) \
               or (0xff00 <= cc <= 0xffef) or (0x20 <= cc <= 0x7e):
                chars.append(chr(cc)); j += 2
            else:
                break
        s = ''.join(chars)
        if 2 <= len(s) <= 30 and any(k in s for k in keywords) and s not in found:
            found.append(s)
        i = j
    else:
        i += 2
# found 即节点名列表；再与文档正文描述交叉验证（本案例与文字 100% 吻合）
```

实测效果：提取出 `政务云 / 政务外网 / 办公网 / 设备网 / 室外设备网 / 核心交换机 /
汇聚交换机 / 接入交换机 / 办公终端 / 设备终端 / 市民活动中心`，与文档文字
"二层结构办公网+设备网、室外三层结构"完全对应。

## EMF 文件头解析（防误判）

- offset 0: `iType=1` (EMR_HEADER)
- offset 4: `nSize` — **是 header 记录大小（如 108），不是整个文件大小**。
  `nSize != 文件字节数` ≠ 截断，勿据此判定文件损坏。
- offset 40 (0x28): `dSignature` 应为 `b' EMF'`（`20 45 4d 46`）——解析偏移时
  从 36 读会读到 rclFrame 内容，是初学陷阱。

## 坏图验证（像素级，勿轻信视觉模型）

vision 模型报"纯黑/空白"时，先做像素统计再下结论——可能是图真坏（源文档问题），
也可能是视觉模型读取失败（格式/显示问题）。区分方法：

```python
from PIL import Image
import numpy as np
img = Image.open("image1.png").convert("RGBA")   # P 模式需先转 RGBA
arr = np.array(img)
for i, name in enumerate(["R","G","B","A"]):
    ch = arr[:,:,i]
    print(f"{name}: min={ch.min()} max={ch.max()} mean={ch.mean():.1f}")
alpha = arr[:,:,3]
print(f"alpha==0: {(alpha==0).mean()*100:.1f}%, alpha==255: {(alpha==255).mean()*100:.1f}%")
```

判定（2026-08 修正——勿重蹈 P-mode 透明 PNG 误判）：
- **不透明像素 100% 为 (0,0,0) + 高透明占比** → **先垫白底修复再判**。
  P mode 透明 PNG（调色板索引 0 透明且 RGB 黑）实为「透明背景+黑色线条」图——
  Word 默认白底显示正常，但 PIL 转 RGBA 后背景透明、vision 模型黑底渲染
  → 只见黑线，误判"坏图"。**修复（必做）**:
  ```python
  from PIL import Image; import numpy as np
  img = Image.open(p).convert("RGBA")
  arr = np.array(img)
  mask = arr[:,:,3] > 0
  white = np.where(mask[:,:,None], arr, 255)   # 透明→白
  Image.fromarray(white.astype(np.uint8)).save(out)  # 再用 out 做 vision_analyze
  ```
  本次实测：image1.png 初判"源文档坏图"，用户指出 Word 正常显示 → 垫白底后
  vision 完整识别出光纤拓扑（中心=市民活动中心机房 + 9 节点 + 实/虚线图例）。
- **真坏图三条件（须同时满足）**：透明>90% **且** 不透明像素全黑 **且**
  垫白底后 vision 仍无内容 → 才判源文档坏图，内容不可恢复，报告建议向提供方
  索要原图。
- 像素有内容但 vision 读不出 → 换 PNG 转换/二进制解析，勿判源图损坏。
