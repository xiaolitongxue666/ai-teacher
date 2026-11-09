# Dify 路线

Dify 里做教育知识库，目标是**给 RAG 准备高质量数据**，不是「让 AI 操作文件」。这个定位差别决定了两条技术路线完全不同。

## 一、结论

| 你的云存储 | 用什么 |
| --- | --- |
| OneDrive / Google Drive / Box / AWS S3 / 腾讯 COS / Dropbox / Azure Blob / SharePoint | **官方 datasource 插件**，插件市场直接装 |
| 坚果云 / Nextcloud / ownCloud 等 WebDAV | 知识库数据源：社区插件 `shaba/dify-datasource-webdav`，或本地同步后手动上传；工作流内取文件：官方 `nextcloud` tool 插件 |
| 扫描版 PDF 解析 | **MinerU 官方插件**（首选） |
| 中文 OCR / 需自托管 | **PaddleOCR 官方插件** |

**最顺畅的组合**：官方云存储数据源 + MinerU。这是唯一全程不脱离 Dify 生态的方案。

---

## 二、官方数据源（已核实）

从 `langgenius/dify-official-plugins` 的 `datasources` 目录直接读取，当前包含：

```
aws_s3_storage          google_drive          notion_datasource
azure_blob              google_cloud_storage  onedrive
box_datasource          github                sharepoint_datasource
brightdata_datasource   gitlab_datasource     tavily_datasource
confluence_datasource   jina_datasource       tencent_cos_storage
dropbox_datasource      firecrawl_datasource
```

**原始推荐里说的「OneDrive、Google Drive、Box、AWS S3、腾讯 COS」全部确认存在。**

配置方式：Dify → 知识库 → 数据源 → 选择对应插件 → 填凭据 → 浏览文件夹 → 选择文件 → 摄取（ingest）。

---

## 三、WebDAV：需要修正的认知

原始推荐说「WebDAV Datasource 是 Dify 生态中接入任意网盘的事实标准方案」。

**实际情况：官方 `datasources` 目录里没有任何 webdav 条目。**

但要区分清楚：官方 `tools` 目录里有一个 `nextcloud` 插件（`langgenius` 作者，v0.1.7），描述写明「manage files, folders and access shared content via **WebDAV**」，提供 `list_files` / `download_file` / `upload_file` / `create_folder` / `delete_file` / `search_files` 六个工具。

它是 **tool 插件，不是 datasource**。区别在于：tool 插件只能在工作流/Agent 节点里被调用，不能出现在「知识库 → 数据源」的摄取列表里。所以它解决不了「把网盘文件直接灌进知识库」，但能解决「工作流里按路径取文件」。

真正要接知识库数据源，能用的只有社区插件：

| 项 | 值 |
| --- | --- |
| 仓库 | `shaba/dify-datasource-webdav` |
| 星数 | **1** |
| 功能 | 浏览并摄取任意 WebDAV 服务器上的文件 |

它不是「事实标准」，是「社区方案里唯一的选择」。1 star、单人维护，Dify 升级后需要自己跟进兼容性。

### 三个可选路径

**路径 A：用社区插件**

安装后在配置里填：

```
base_url:  https://dav.jianguoyun.com/dav/
username:  你的账号
password:  应用密码（不是登录密码）
```

坚果云的 `base_url` 是固定的。其他 WebDAV 服务换成各自的地址。

**路径 B：本地同步 + 手动上传**

如果你的核心诉求是「坚果云里的资料进知识库」，不一定非要插件：

1. 用坚果云客户端把文件夹同步到本机；
2. 在 Dify 知识库里直接上传本地文件；
3. 后续更新用坚果云客户端同步，再在 Dify 里重新上传变更的部分。

这条路少一层依赖，但多一步手工。资料量不大时更划算。

**路径 C：Cursor 里处理完再上传**

用 [../mcp/README.md](../mcp/README.md) 里的 `webdav-mcp-server` 把文件拉到本地，用 `pymupdf4llm-mcp` 转成 Markdown，再上传到 Dify。

适合"文件质量差、需要先清洗"的场景——先把 PDF 转成干净的 Markdown，知识库的检索质量会明显提升。

---

## 四、PDF OCR：MinerU 是官方插件

同样从官方仓库 `tools` 目录确认：

```
tools/
├── mineru          ✅
├── paddleocr       ✅
├── nextcloud       ✅（WebDAV，但只能在工作流里调用）
├── feishu_document
└── lark_document
```

### MinerU 为什么适合教育资料

| 特性 | 对教育场景的意义 |
| --- | --- |
| 自动检测扫描版 PDF 并启用 OCR | 老教材、影印版试卷不用手动区分 |
| 支持 84 种语言 | 中英混排的教材直接吃 |
| 复杂 PDF（公式、表格、多栏）还原为结构化 Markdown/JSON | 数学教材的公式、英语教材的多栏排版不会被打乱 |

**这一点在数学资料上尤其重要**。几何教材里大量公式和图形标注，普通 PDF 解析会把两栏文字串成一行，检索出来的片段毫无意义。MinerU 保留版面结构，切出来的 chunk 才有用。

### 备选：PaddleOCR

官方插件，中文识别有优势，可自托管（数据不出内网）。

适合场景：资料以中文为主、对数据主权有要求、或者 MinerU 的云端版不符合你的隐私要求。

### Upstage Document Parse

**官方插件目录里没有找到。** 标注为「第三方/未核实」。

如果你的信息源有具体链接，欢迎提 issue 补充。

---

## 五、教育知识库的预处理建议

这些是从实际使用中总结的，不是官方文档里的内容。

### 1. 先分类型，再进知识库

不要把「教材 PDF」「试卷 PDF」「单词表」混在一个知识库里。

| 资料类型 | 切分策略 | Chunk 大小 |
| --- | --- | --- |
| 教材 | 按章节/小节 | 800-1200 字符 |
| 试卷 | 按题目 | 按题切分，一题一块 |
| 单词表 | 按单元 | 200-400 字符 |
| 短文阅读 | 按篇 | 一篇一块，不要切 |

统一 chunk 大小是常见错误。教材和单词表的合理粒度差 3 倍。

### 2. 扫描件先转 Markdown 再入库

MinerU 输出的 Markdown 比直接切 PDF 文本好，因为它保留了结构。用 Markdown 进知识库，检索命中的片段自带标题层级，LLM 能判断这段属于哪一节。

### 3. 给每份资料加元数据

Dify 的知识库支持元数据。至少加：

- `科目`：英语 / 数学 / 科学
- `年级`：1-6 / 初中 / 高中
- `资料类型`：教材 / 练习 / 单词表

这样检索时可以先用元数据缩小范围，再语义匹配，命中率高得多。

### 4. 别把网盘的整个目录都灌进去

网盘里的资料往往有大量重复（同一套教材的不同版本、重复的练习册）。先人工筛一遍，把「要用的」挑出来再进知识库。

重复内容会污染检索结果——同一段文字在三个文件里出现，检索时三个都命中，占满上下文。

---

## 六、和 Cursor 路线的分工

| 你要做的事 | 用哪条路线 |
| --- | --- |
| 临时看一个 PDF 讲了什么 | Cursor + `pymupdf4llm-mcp` |
| 批量清理教材、转 Markdown | Cursor + MCP，脚本化 |
| 给孩子做一个能问答的知识库 | Dify + MinerU |
| 从网盘直接摄取到知识库 | Dify + 官方数据源（或 WebDAV 社区插件） |
| 做一个自动批改/出题的 Agent | Dify 工作流 |

简单说：**Cursor 是加工车间，Dify 是成品应用**。先在 Cursor 里把资料洗干净，再进 Dify。
