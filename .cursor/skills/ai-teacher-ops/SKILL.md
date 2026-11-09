---
name: ai-teacher-ops
description: Maintain the ai-teacher learning-resource index repo — add or verify links, register a Quark share collection with measured file counts, run the link/Quark probes, and commit. Use when adding a resource to data/resources.json, editing docs/02 03 03b 07, running scripts/check_links.py or scripts/download_video.py, or when a link needs re-verification.
disable-model-invocation: true
---

# ai-teacher 运营流程

本仓是**链接索引**，不是课程、不托管文件。所有改动都要落到两条硬约束上：

1. `data/resources.json` 是唯一数据源，文档里的数字必须能从它推出来；
2. 每条链接同时有 `verified` 与 `checked_at`，二者都不能手填。

## 快速开始

```bash
python scripts/check_links.py                    # 全量报告，不改文件
python scripts/check_links.py --only websites    # 只看网站
python scripts/check_links.py --only quark_tree  # 只统计夸克分享目录
python scripts/check_links.py --write            # 回写 verified / checked_at / final_url
```

执行前先设 `PYTHONIOENCODING=utf-8`，否则中文输出在 Windows 控制台是乱码。

## 三个工作流

### 工作流 A：新增一条网站 / 仓库链接

1. 追加到 `data/resources.json` 对应分区，`verified` 写 `pending`，`checked_at` 留空。
2. 跑 `check_links.py --only <分区> --write`，让脚本填值。
3. 把结果同步进 `docs/03-参考网站.md`（网站）或 `docs/07-开源项目清单.md`（仓库）的表格。
4. 如果分区总数变了，同步 `docs/00-使用说明.md` 的分区计数表与 `README.md` 的索引表。

**不要**手写 `verified: ok`。仓库已有 14 条星数漂移是历史遗留，别再制造第二种漂移。

### 工作流 B：登记一条网盘分享

先判断入口类型，再取实测数据。

```bash
# 1. 中转页解析出官方分享 id（跟 302 与 meta refresh）
python -c "import urllib.request;print(urllib.request.urlopen(urllib.request.Request('<中转链接>',headers={'User-Agent':'Mozilla/5.0'})).geturl())"

# 2. 读全目录，拿文件数、总大小、扩展名分布
python scripts/check_links.py --only quark_tree --write
```

写进 `collections` 的字段（详见 [reference.md](reference.md)）：

- `url_official` 官方直链；`url_alias` 第三方中转（正文只登官方页，别名只记在 `collections/`）
- `entry_type` 写清是「官方直链」还是「第三方中转页 + 跳转方式」
- `share_total_files` / `share_total_size_bytes` / `share_suffix_counts` 由脚本回写
- `share_tree_truncated` / `share_tree_incomplete` 为真时，`share_total_files` 是**下限**，文档必须写明「≥N」

然后改三处文档：`docs/03b-网盘资料清单.md` 加条目段落、`collections/网盘分享链接.md` 记原始链接、`docs/02-科目类别.md` 挂锚点入口。

### 工作流 C：视频下载

```bash
python scripts/download_video.py --check
python scripts/download_video.py <URL> [--audio-only] [--output DIR]
```

网盘分享链接会被脚本直接拒绝——`yt-dlp` 1755 个提取器里国内网盘命中 0。网盘里的 mp4 必须先用网盘客户端或 `BaiduPCS-Go` 落盘。

## 不要做什么

| 禁止 | 原因 |
| --- | --- |
| 手填 `verified` / `checked_at` | 违反「先验证再呈现」。要么跑脚本，要么标 `pending` |
| 把请求超时当成「目录到底了」 | 会导致静默漏数，实测同一分享两次统计差 40 个文件 |
| 覆盖人工标记的 `mismatch` | `mismatch` 表示链接可达但内容不符，是判断结论不是探测结果 |
| 在正文里写第三方中转域名 | 中转站会消失，正文只登官方分享页 |
| 转述原始文案里的数量（「900 节」「57 种工具」） | 要么实测过，要么在 `note` 里写明「原文案，未核对」 |
| 提交 Cookie / token / 可执行文件 | 凭据进 `.credentials/`（已忽略），二进制进 `.tools/`（已忽略） |
| 把 5 分钟没跑完的遍历结果当完整值 | 置 `share_tree_truncated`，文档写「≥N」 |

## 环境约定

- 工作副本只有 `E:\Code\my_code\Agents\ai-teacher` 一份，别再开第二份。
- bash 里盘符写 `/e/...`，不要用 `cmd //c`。
- Python 输出中文一律 `PYTHONIOENCODING=utf-8`。
- 跨 bash 与 python 传文件用项目内相对路径，用完即删；`/tmp` 两边解析到不同位置。
- 提交前跑 `git-smart-commit --yes`，它会拦 `logs/`、`__pycache__/`、`.credentials/`、`.tools/` 等。
- 推送被拒时不要直接 rebase：`data/resources.json` 改动密集，必然冲突。先 `git fetch` 看范围，必要时 `reset --hard origin/main` 后重放。

## 更多

字段字典、`verified` 六种取值、完整踩坑清单见 [reference.md](reference.md)。
