# lan-yu-data

蓝鱼工作台的每日数据采集仓库。GitHub Actions 每天北京时间 08:00 跑一次。

## 采集什么

| 数据 | 来源 | 范围 |
|---|---|---|
| 抖音日榜 | TikHub 视频热榜 API | 7 个赛道 × 前 5 条（播放/点赞/点赞率/涨粉） |
| 亚马逊榜单 | Amazon Best Sellers 公开页 | 4 个类目 × 前 20 条（价格/评分/评论数/ASIN） |

结果写到 `data/latest.json`，自动 commit 回仓库。

## 还差一步：加工作流文件

`.github/workflows/daily.yml` 需要手动加一下（API 写入需要 `workflow` 权限）：

1. 打开 https://github.com/xushan628/lan-yu-data/new/main
2. 文件名处直接输入：`.github/workflows/daily.yml`（输斜杠会自动建目录）
3. 把本地 `github-actions/.github/workflows/daily.yml` 的内容整段粘进去
4. 底部 Commit changes

## 还要配两件事

**1. 加 Secret**

Settings → Secrets and variables → Actions → New repository secret

- Name: `TIKHUB_API_KEY`
- Secret: TikHub 后台拿的 API Key

**2. 开写权限**

Settings → Actions → General → Workflow permissions → 选 **Read and write permissions** → Save

（不开这个，脚本跑完了也 commit 不回来）

## 跑一次看看

Actions → 左侧「每日采集」→ Run workflow

成功后根目录会出现 `data/latest.json`。

## 数据链接

```
https://raw.githubusercontent.com/xushan628/lan-yu-data/main/data/latest.json
```

本地工作台用 `python tools/apply_latest.py <这个链接>` 就能直接读入。

## 已知限制

- **亚马逊可能失败**：Actions 是机房 IP，亚马逊大概率给验证码。失败时脚本会沿用上次数据，不写空文件。
- **TikHub 免费额度 50 次**：7 赛道 = 7 次/天，约一周用完，之后需充 $5。
- 仓库是 Public，数据也公开。数据本身都是公开信息；如果介意可以改 Private 并配 token。
