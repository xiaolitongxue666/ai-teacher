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

## 逐个工具的详细信息

安装命令、版本、仓库、核验状态、风险评级，见 [../docs/04-工具推荐.md](../docs/04-工具推荐.md)。

这里只列结论：

| 工具 | 注册表 | 版本 | Key | 平台 | 风险 |
| --- | --- | --- | --- | --- | --- |
| `webdav-mcp-server` | npm | 1.0.4 | 是 | 全平台 | 低 |
| `sync-vault-agent` | npm | 0.2.1 | 是 | 全平台 | **中高** |
| `@ptbsare/netdisk-mcp-server` | npm | 1.1.1 | 是 | 全平台 | 中 |
| `pymupdf4llm-mcp` | PyPI | 1.28.0 | 否 | 全平台 | 低 |
| `pdffr-mcp` | npm | 0.1.1 | 否 | 全平台 | 低 |
| `mcp-pdf` | PyPI | 2026.9.22 | 否 | 全平台 | 低 |
| `macos-vision-mcp` | npm | 0.7.0 | 否 | **仅 macOS** | 低 |
| `fastocr-mcp` | PyPI | 0.3.0 | **是** | 全平台 | 中（数据上云） |
| `ocr-mcp` | PyPI | 0.1.0 | 视后端 | 全平台 | 中（版本很早期） |
| `mcp-onedrive` | npm | 0.10.2 | 是 | 全平台 | 中 |

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
