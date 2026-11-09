# Cursor MCP 配置

网盘下载与 PDF OCR 的 MCP 配置。**这里只放模板，不会自动改你的 `~/.cursor/mcp.json`**，需要你自己拷。

## 先确认一下你需要的

| 你的网盘 | 选哪个 | 理由 |
| --- | --- | --- |
| 坚果云 / Nextcloud / ownCloud / NAS | `webdav-mcp-server` | 通用 WebDAV，最稳 |
| 百度 / 阿里 / 115 / 夸克 / OneDrive（多个） | `sync-vault-agent` | 唯一全覆盖，但需谨慎 |
| 只用夸克 / 115 | `@ptbsare/netdisk-mcp-server` | 专用，比全覆盖工具可控 |
| 只用 OneDrive | `mcp-onedrive` | 专用 |

| 你的 PDF | 选哪个 |
| --- | --- |
| 数字版（有文字层） | `pymupdf4llm-mcp`（首选）或 `pdffr-mcp` |
| 扫描版（无文字层） | `mcp-pdf`（含 OCR）或 `pdffr-mcp` |
| 版式复杂（公式/表格/多栏） | `mcp-pdf`，或改用 MinerU |
| 在 Mac 上、要完全离线 | `macos-vision-mcp` |

---

## 配置位置

两个位置，按需选：

| 位置 | 作用范围 | 适合 |
| --- | --- | --- |
| `~/.cursor/mcp.json` | 这台机器上所有项目 | 长期使用的工具 |
| `<项目>/.cursor/mcp.json` | 只在当前项目生效 | 试验新工具、项目专用配置 |

当前机器 `~/.cursor/mcp.json` 是空的（`{"mcpServers": {}}`），可以直接往里加。

---

## 模板一：最保守的组合（推荐起点）

只用本地、无 Key、不经过第三方的工具。

```json
{
  "mcpServers": {
    "pdf-markdown": {
      "command": "uvx",
      "args": ["pymupdf4llm-mcp"]
    },
    "webdav": {
      "command": "npx",
      "args": ["-y", "webdav-mcp-server"],
      "env": {
        "WEBDAV_ROOT_URL": "https://dav.jianguoyun.com/dav/",
        "WEBDAV_ROOT_PATH": "/",
        "WEBDAV_AUTH_ENABLED": "true",
        "WEBDAV_USERNAME": "your@email.com",
        "WEBDAV_PASSWORD": "应用密码，不是登录密码"
      }
    }
  }
}
```

**说明**

- `uvx` 需要先装 `uv`（本机已装 0.9.2）；
- 坚果云的 WebDAV 地址固定是 `https://dav.jianguoyun.com/dav/`；
- 应用密码在坚果云「账户信息 → 安全选项 → 添加应用」生成。**用登录密码会认证失败**；
- 变量名以 `LaubPlusCo/mcp-webdav-server` 的 README 为准：是 `WEBDAV_ROOT_URL` 而非 `WEBDAV_URL`，且必须显式 `WEBDAV_AUTH_ENABLED=true` 才会带上凭据。`WEBDAV_PASSWORD` 只能是明文，因为 WebDAV 协议要求把密码发给服务端。

---

## 模板二：要接国产网盘

```json
{
  "mcpServers": {
    "pdf-markdown": {
      "command": "uvx",
      "args": ["pymupdf4llm-mcp"]
    },
    "pdf-ocr": {
      "command": "uvx",
      "args": ["mcp-pdf"]
    },
    "vault": {
      "command": "npx",
      "args": ["-y", "sync-vault-agent"]
    }
  }
}
```

**说明**

- `sync-vault-agent` 首次运行需要 `mcp-agent init` 走 OAuth 授权流程，不是纯 JSON 能配完的。先在终端跑一次初始化：
  ```bash
  npm i -g sync-vault-agent
  mcp-agent init
  ```
- 授权时**用小号网盘账号**。这个包 2026-07 才发布，仓库 0 star，没有第三方验证。
- 如果只接夸克或 115，换成 `@ptbsare/netdisk-mcp-server`，风险更可控。它不需要走 OAuth，而是直接读 Cookie：

  ```json
  {
    "mcpServers": {
      "netdisk": {
        "command": "npx",
        "args": ["-y", "@ptbsare/netdisk-mcp-server"],
        "env": {
          "NETDISK_QUARK_COOKIE": "替换为夸克网盘 Cookie",
          "NETDISK_115_COOKIE": "替换为 115 网盘 Cookie",
          "PANSOU_URL": "http://your-pansou-instance"
        }
      }
    }
  }
  ```

  `PANSOU_URL` 只有用 `search` 工具才需要，不填也能用 `list` / `view` / `transfer`。

---

## 模板三：轻量 PDF 处理

```json
{
  "mcpServers": {
    "pdffr": {
      "command": "npx",
      "args": ["-y", "pdffr-mcp"]
    }
  }
}
```

提供三个工具：

| 工具 | 作用 |
| --- | --- |
| `pdf_to_markdown` | PDF 转 Markdown |
| `pdf_outline` | 提取目录结构 |
| `pdf_tables` | 提取表格 |

**注意**：这个包**只在 npm**，PyPI 上不存在。用 `npx`，不要用 `uvx`。

---

## 验证配置是否生效

1. 保存 `mcp.json` 后，在 Cursor 设置里打开 MCP 面板（`Cmd/Ctrl + Shift + P` → 搜 `MCP`）；
2. 应该看到新加的服务，状态为绿灯；
3. 如果红灯，点开看日志。最常见的两个错误：
   - `spawn uvx ENOENT`：`uv` 没装或不在 PATH；
   - `401 Unauthorized`：WebDAV 用了登录密码而不是应用密码。

**首次启动会下载依赖**。`npx` 类工具第一次跑要几十秒，别以为是卡死了。

---

## 实测结论：netdisk MCP 的真实能力边界

2026-11-09 用 MCP 协议直接连 `@ptbsare/netdisk-mcp-server@1.1.1` 实测，以下都是抓到的实际返回，不是文档转述。

### 六个工具，没有下载

```
list_tools -> ['list', 'view', 'transfer', 'offline_download', 'search', 'health']
```

**没有任何 download 工具。** `transfer` 是把分享转存进你自己的网盘，不是落到本地磁盘。

### `view` 免登录可用，但固定只回 100 条

`view` 读公开分享不需要 Cookie，这点很好用。但它**不翻页**：

| 分享 | 实际文件数 | `view` 返回 | 首行声明 |
| --- | --- | --- | --- |
| `668920790b03`（范老师几何） | 910 | 100 | `Total: 100 files (2.00 GB)` |
| `cbd38d7f7061`（1000 词） | 4 | 4 | `Total: 4 files (169.13 MB)` |

第一行的 `Total` 是**服务端单页返回的条数**，不是分享总数。小分享恰好对上，大分享会严重低估。

源码里内部传的是 `_size: '1000'`，但夸克服务端硬限 100 且不翻页，所以拿不到全量。要全量必须自己翻页，见 `scripts/check_links.py` 的 `quark_tree` 分区。

另一处坑：`view` 只扫**分享根目录下一层**。传 `file_pattern="*.zip"` 返回 `No files found`，而那个 zip 其实在子目录里（`700_电子档资料.zip`）。`file_pattern="*"` 能看到它，因为返回的每行带方括号标注了所在目录。

### `list` 没有 Cookie 直接 401

```
list(cloud="quark", path="/") -> Error: Request failed with status code 401
```

`list` 读的是**你自己网盘**，必须有 Cookie。而 `view` 读的是**别人的公开分享**，不需要。

### 项目内的凭据隔离方案

`.cursor/mcp.json` 里不写 Cookie，改成调启动器：

```json
{
  "mcpServers": {
    "netdisk": {
      "command": "python",
      "args": ["scripts/run_netdisk_mcp.py"]
    }
  }
}
```

`scripts/run_netdisk_mcp.py` 从 `.credentials/netdisk.env` 读 `KEY=VALUE`，注入子进程环境。好处：

- 明文 Cookie 只在 `.credentials/` 一处，该目录已被 `.gitignore` 忽略；
- 缺 Cookie 也能启动（`view` 仍可用），只在 stderr 打一行提示；
- 换 Cookie 不用动 MCP 配置。

---

## 百度这条路：官方托管 SSE 与 BaiduPCS-Go

`docs/04` 原先写「百度网盘 MCP 在生态里没有可用的落地物」。这是错的，实测有两条路。

### 官方 `baidu-netdisk/mcp`

百度官方组织下的仓库（163 star，MIT，push 2025-09-23）。但**它不是本地 MCP server**，是远程托管 SSE：

```
https://mcp-pan.baidu.com/sse?access_token=<你的 token>
```

无效 token 实测返回：

```
400 {"errno":2003,"show_msg":"auth fail:token fail"}
```

仓库 README 里那段 Windows 的 `netdisk.py` 配置**指向不存在的文件**（全仓搜 `netdisk.py` 命中 0），只有 client demo 和本地 uploader。要接这个，得先去[开放平台](https://pan.baidu.com/union/home)建应用拿 `AppKey`/`SecretKey` 并配 `redirect_uri` 走 OAuth。

### `BaiduPCS-Go`（本次采用）

| 项 | 值 |
| --- | --- |
| 仓库 | `qjfoidnh/BaiduPCS-Go` |
| 星数 | 5,907 |
| License | Apache-2.0 |
| 版本 | v4.0.2（2026-08-21） |
| 平台 | 有 `windows-x64.zip` |
| 鉴权 | `login -cookies=<Cookie>` 或 `-bduss=<BDUSS> -stoken=<STOKEN>` |

**它不是 MCP**，agent 只能通过 shell 调用。命令面：`ls` / `download` / `transfer`（转存分享）/ `share list`。

实测未登录状态：

```
BaiduPCS-Go --version  -> BaiduPCS-Go version v4.0.2
BaiduPCS-Go who        -> uid: 0, 用户名: (空)
BaiduPCS-Go ls /       -> not absolute path
```

二进制放 `.tools/`，已忽略，不入库（`docs/00` 贡献约定第 5 条禁止提交可执行文件）。

---

## 取 Cookie 的两条路都已被 Chrome 封堵

这是本次核实推翻的第二个假设。你的 Chrome 是 `156.0.8078.81`，默认 profile 且未带 `--user-data-dir`。

| 原方案 | 结论 |
| --- | --- |
| `--remote-debugging-port` 重启 Chrome 抽 Cookie | **Chrome ≥136 在默认 profile 上直接忽略该开关**，端口不开。官方公告要求必须配 `--user-data-dir` 指向非默认目录 |
| 复制 profile 到临时目录再起调试 | App-Bound Encryption 对非默认目录返回 `kTemporarilyUnavailable`，v20 Cookie 解不开。见 `app_bound_encryption_provider_win.cc` 的 `kNotUsingDefaultUserDataDir` 分支 |
| 直接读 `Network/Cookies` | Chrome 运行时文件被独占锁，实测 `PermissionError: [Errno 13]` |

所以 Cookie 只能**手动从 DevTools 复制**到 `.credentials/netdisk.env`。

---

## 逐个工具的详细信息

安装命令、版本、仓库、核验状态、风险评级，见 [../docs/04-工具推荐.md](../docs/04-工具推荐.md)。

这里只列结论：

| 工具 | 注册表 | 版本 | Key | 平台 | 风险 |
| --- | --- | --- | --- | --- | --- |
| `webdav-mcp-server` | npm | 1.0.4 | 是 | 全平台 | 低 |
| `sync-vault-agent` | npm | 0.2.1 | 是 | 全平台 | **中高** |
| `@ptbsare/netdisk-mcp-server` | npm | 1.1.1 | 是 | 全平台 | 中（无 download 工具） |
| `pymupdf4llm-mcp` | PyPI | 1.28.0 | 否 | 全平台 | 低 |
| `pdffr-mcp` | npm | 0.1.1 | 否 | 全平台 | 低 |
| `mcp-pdf` | PyPI | 2026.9.22 | 否 | 全平台 | 低 |
| `macos-vision-mcp` | npm | 0.7.0 | 否 | **仅 macOS** | 低 |
| `fastocr-mcp` | PyPI | 0.3.0 | **是** | 全平台 | 中（数据上云） |
| `ocr-mcp` | PyPI | 0.1.0 | 视后端 | 全平台 | 中（版本很早期） |
| `mcp-onedrive` | npm | 0.10.2 | 是 | 全平台 | 中 |
| `BaiduPCS-Go` | GitHub Release | v4.0.2 | 是（Cookie） | Win/macOS/Linux | 中（**非 MCP**，CLI） |
| `yt-dlp` | PyPI | 2026.10.26 | 否 | 全平台 | 低（**非 MCP**，CLI） |

---

## 视频下载：yt-dlp 是唯一解，但它进不了网盘

| 项 | 值 |
| --- | --- |
| 包名 | `yt-dlp` |
| 仓库 | `yt-dlp/yt-dlp`（206,288 star，Unlicense） |
| 版本 | `2026.10.26` |
| 运行 | `uvx yt-dlp <URL>` |

实测 **1755 个提取器**，B站与 YouTube 都能下。项目内封装见 `scripts/download_video.py`。

### 它下不了国内网盘

实测在提取器列表里搜夸克、百度、阿里、115、迅雷、天翼、彩云，**全部命中 0**：

```
quark 0   baidu 1(BaiduVideo，是视频站不是网盘)   aliyun 0
115   0   xunlei 0   tianyi 0   caiyun 0
```

所以「网盘里的 mp4 怎么下」这个问题，yt-dlp 回答不了。实际分工：

| 场景 | 用什么 |
| --- | --- |
| B站 / YouTube / 公开视频站 | `yt-dlp` |
| 夸克网盘 | 网盘客户端（无可用 CLI） |
| 百度网盘 | `BaiduPCS-Go download` |
| 转存到自己的账号 | `netdisk` MCP 的 `transfer` |

### Windows 上 Cookie 这条路走不通

`--cookies-from-browser chrome` 在本机直接报错：

```
ERROR: Could not copy Chrome cookie database.
```

两层限制叠加，都已实测确认：

1. Chrome 运行**独占锁** `Network/Cookies`，直接读报 `PermissionError: [Errno 13]`；
2. 用 VSS 卷影复制能绕过第一层（需管理员权限，实测拿到 2MB 快照），但本机 **3446 条 Cookie 全是 v20**（App-Bound Encryption）。v20 主密钥要先用 SYSTEM 权限 DPAPI 解一层，用户态进程无解。

对照实验：`v10` 的 `encrypted_key` 能用用户级 DPAPI 解出 32 字节 AES key，`v20` 的 `app_bound_encrypted_key` 则解不开。这是 Chrome 防 infostealer 的核心设计，不是配置问题。

yt-dlp 维护者在 [issue #15401](https://github.com/yt-dlp/yt-dlp/issues/15401) 明确表示没有修复计划，已移除 Windows 上 Chrome 的该支持。

自检命令：

```bash
python scripts/check_chrome_cookies.py
```

**别套 `timeout`**：MSYS 的 `timeout` 会丢 `LOCALAPPDATA`，脚本定位不到 Chrome 目录。

替代：浏览器扩展导出 `cookies.txt` 后用 `--cookies`，或改用 Firefox。`cookies.txt` 是登录态明文，别放进项目目录。

---

## 三个容易踩的坑

### 1. 包名撞车

npm 上的 `pdf-mcp` 是**删 PDF 页面**的工具，不是 PDF 解析工具。功能全的那个在 PyPI 上，叫 `mcp-pdf`。

### 2. 注册表搞错

| 包 | 在 npm | 在 PyPI |
| --- | --- | --- |
| `pdffr-mcp` | 有 | **无** |
| `nutstore-mcp` | **无** | 有 |
| `fastocr-mcp` | **无** | 有 |
| `mcp-pdf` | **无** | 有 |

写错注册表，`npx` / `uvx` 会直接 404。

### 3. Windows 下 `npm i -g` 报配置冲突

```
npm error config prefix cannot be changed from project config
```

`~/.npmrc` 与项目级 npm 配置冲突。查询类命令（`npm view`）不受影响，但 `npm i -g` 会失败。

检查方式：

```bash
npm config get prefix
```

确保 `~/.npmrc` 里的 `prefix` 是绝对路径，且项目目录下没有重复定义 `prefix` 的 `.npmrc`。
