# Stock App Automation (同花顺 on macOS)

A worked example of driving the 同花顺 (Tonghuashun) native macOS stock-trading
app using the cua-driver CLI fallback, extracting structured data via
`vision_analyze`, and piping results into messaging (WeChat).

## Architecture

```
cron schedule (e.g. every 30 min during trading hours)
  │
  ├─ cua-driver call launch_app  → ensure 同花顺 is running
  ├─ cua-driver call get_window_state → screenshot + AX tree
  ├─ Python decode base64 → /tmp/ths_screenshot.png
  ├─ vision_analyze(/tmp/ths_screenshot.png)
  │     → structured stock data (prices, change %, signals)
  └─ send_message(target="weixin", message=formatted_report)
```

## Prerequisites

- 同花顺.app installed at `/Applications/同花顺.app`
- cua-driver installed and permissions granted (Accessibility + Screen Recording)
- cua-driver binary at `/Applications/CuaDriver.app/Contents/MacOS/cua-driver`
- WeChat gateway configured (optional, for push delivery)

## Step-by-Step Workflow

### 1. Find and launch 同花顺

```bash
CUADRIVER=/Applications/CuaDriver.app/Contents/MacOS/cua-driver

# Find the bundle ID
osascript -e 'id of app "同花顺"'
# → cn.com.10jqka.IHexin

# Launch (background, does NOT bring to front)
$CUADRIVER call launch_app '{"bundle_id": "cn.com.10jqka.IHexin"}'
```

The response includes a `pid` — save it for subsequent commands.

### 2. Find the window

Wait a few seconds for the app to fully render, then:

```bash
$CUADRIVER call list_windows '{}'
```

Look for the entry with `"app_name": "同花顺"`. Note its `pid` and `window_id`.

**Pitfall:** On first launch, `get_window_state` may return
`element_count: 0` and `"could not create image from window"`. Retry after
5-10 seconds — the window needs time to render.

### 3. Capture the window state (screenshot + AX tree)

```bash
$CUADRIVER call get_window_state '{"pid": 83896, "window_id": 1144}'
```

Returns JSON containing:
- `screenshot_png_b64`: base64-encoded PNG
- `tree_markdown`: AX element tree with indices (e.g. `[3] AXStaticText (自选)`)
- `element_count`: number of AX elements

### 4. Decode the screenshot for vision analysis

The large base64 blob in the JSON response is best handled with Python:

```bash
$CUADRIVER call get_window_state '{"pid": 83896, "window_id": 1144}' |
  python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
with open('/tmp/ths_screenshot.png', 'wb') as f:
    f.write(base64.b64decode(data['screenshot_png_b64']))
print(f'Saved, elements={data.get(\"element_count\",0)}')
"
```

### 5. Navigate to the watchlist (自选股) page

同花顺 typically opens to the 首页 (home) page. Switch to 自选股:

```bash
# Step A: get_window_state to populate element cache
$CUADRIVER call get_window_state '{"pid": 83896, "window_id": 1144}'

# Step B: find the element index for "自选" tab — search the AX tree
# The element index may differ between captures, so always look for it:
$CUADRIVER call get_window_state '{"pid": 83896, "window_id": 1144}' |
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for line in data['tree_markdown'].split(chr(10)):
    if '自选' in line and 'StaticText' in line:
        print(line.strip())
"
# → e.g. [3] AXStaticText (自选)

# Step C: click the "自选" tab (using the index found above)
$CUADRIVER call click '{"pid": 83896, "window_id": 1144, "element_index": 3}'
sleep 2

# Step D: re-capture to confirm navigation succeeded
$CUADRIVER call get_window_state '{"pid": 83896, "window_id": 1144}' |
  python3 -c "import sys,json; d=json.load(sys.stdin); open('/tmp/ths_zixuan.png','wb').write(__import__('base64').b64decode(d['screenshot_png_b64']))"
```

**Pitfall — element cache:** The `click` (and `scroll`, `double_click`,
`right_click`) commands require a prior `get_window_state` call to populate an
internal element cache. If you get `"Element index N not found in cache"`,
call `get_window_state` first, then immediately call `click` using the
same PID/window_id.

### 6. Extract stock data via vision_analyze

```python
vision_analyze(
    image_url="/tmp/ths_zixuan.png",
    question="This is a 同花顺 stock watchlist screenshot. "
             "List every stock with: stock name, stock code, "
             "latest price, change %, GS signal, main fund flow, "
             "turnover rate. Format as a table."
)
```

The vision model reliably reads Chinese stock UI columns including:
- Stock name + code (e.g. 凯格精机 301338)
- Latest price and change % (red/green per Chinese market convention)
- GS signal (技术信号 like 强势线上, 大牛线上)
- Main fund flow (主力资金 in ¥)
- Turnover rate, volume ratio, market cap

### 7. Scroll to see more stocks

If the watchlist has more stocks than fit on screen:

```bash
$CUADRIVER call get_window_state '{"pid": 83896, "window_id": 1144}'
$CUADRIVER call scroll '{"pid": 83896, "window_id": 1144, "direction": "down", "amount": 5}'
sleep 1
# Re-capture
$CUADRIVER call get_window_state '{"pid": 83896, "window_id": 1144}' |
  python3 -c "import sys,json; open('/tmp/ths_scrolled.png','wb').write(__import__('base64').b64decode(json.load(sys.stdin)['screenshot_png_b64']))"
vision_analyze(image_url="/tmp/ths_scrolled.png", question="...")
```

Aggregate results from multiple captures for the full watchlist.

### 8. Format and push to WeChat

```python
report = f"""
📊 自选股盘中监测 {timestamp}

301338 凯格精机  142.05  -4.43%  📉  GS:强势线上
301526 国际复材   28.44  +7.52%  📈  GS:大牛线上
...
"""

send_message(target="weixin", message=report)
```

## Scheduled Execution via Cron

Wrap the full pipeline in a cron job:

```bash
hermes cron create "*/30 9:30-15:00 * * 1-5" \
  --name "同花顺盘中监测" \
  --prompt "Drive 同花顺 on the Mac: launch if needed, capture the watchlist
            screenshot, decode it, extract stock data with vision, and send
            a brief formatted report to WeChat. Stocks: 凯格精机(301338),
            华工科技(000988), 国际复材(301526), 华润三九(000999)."
```

## Key Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Element cache empty | "not found in cache" on click | Call `get_window_state` first with same pid/window_id |
| Window not rendered | "could not create image from window" | Wait 5-10s after launch, retry |
| cua-driver not on PATH | "command not found" | Use full path: `/Applications/CuaDriver.app/Contents/MacOS/cua-driver` |
| Base64 too large for echo | "Argument list too long" | Use Python `json.loads` + `base64.b64decode` instead |
| Vision model misses data | Incomplete stock list | Scroll down and capture multiple screenshots, then merge |
