# zotero-paper-import

[English](README.md) | [简体中文](README.zh-CN.md)

查找论文、下载 PDF，并生成 Zotero 原生导入文件的 Agent Skill。支持 DOI、arXiv 编号与指定版本、URL 和标题搜索；可选使用 OrcaRouter、OpenAI 或兼容接口生成论文摘要。

## 安装

```bash
git clone https://github.com/FidollarinLA/zotero-paper-import.git ~/.cursor/skills/zotero-paper-import
```

其他支持 Skill 的 Agent 可放到对应技能目录。需要 Python 3.10+、curl 和本地 Zotero。可复制 `config.example.md` 为 `config.md`，供 Agent 读取偏好；脚本使用命令行参数，不自动解析配置文件。

## 导入步骤

```bash
python3 scripts/resolve_paper.py --arxiv 2602.03070v5
python3 scripts/download_pdf.py --arxiv 2602.03070v5 --preference any --output ./paper.pdf
python3 scripts/import_to_zotero.py --arxiv 2602.03070v5 --pdf ./paper.pdf --collection "我的论文" --output ./papers.ris --receipt ./preparation.json
```

接着在 Zotero 选择 **文件 → 导入 → 文件**，打开 `papers.ris`，选择复制附件，再把条目加入目标分类。核对条目数、标题、作者、DOI 和 PDF 能否打开。整个过程 Zotero 可以保持运行。脚本只生成 RIS、只读查重和输出逐篇结果及 PDF 哈希，不直接修改数据库，也不自动创建分类。Agent 有可用的界面工具时可以操作原生导入，否则需用户完成这一步。

DOI 元数据来自 Crossref，arXiv 来自其独立 API，保留指定版本并区分预印本与发表 DOI。网络不可用时可通过清单提供核验过的元数据，见 [示例](examples.md)。Unpaywall 需 `--email` 提供真实联系邮箱，未提供则跳过。只要正式版时不会自动换成预印本或接受稿；付费墙下可使用用户合法获得的 PDF。

## 可选 OrcaRouter 摘要

先[注册账号并创建 API Key](https://docs.orcarouter.ai/quickstart)，从当前模型列表选择准确的模型 ID，在本地环境变量设置 `ORCAROUTER_API_KEY`。接口为 `https://api.orcarouter.ai/v1`。不要把 Key 写入仓库或聊天。

```bash
python3 scripts/summarize_paper.py --provider orcarouter --model "<模型列表中的ID>" --input ./abstract.txt --output ./summary.md
```

默认只在本地预览，不需要 Key，不发送请求。用户同意将这段文本发给所选平台并接受可能的费用后，添加 `--send` 执行。不会自动上传 PDF、重试或切换收费模型。也可选 `openai`（环境变量 `OPENAI_API_KEY`），或 `custom --base-url https://your-provider.example/v1`（`LLM_API_KEY`）。基础导入不需要 LLM 账号。AI 摘要需对照原文核验。

作者可申请 [Built with OrcaRouter](https://www.orcarouter.ai/zh-CN/built-with)。合作申请审核和项目专属推荐链接，与 API 接入是两件事。目前仓库尚未配置项目推荐链接；仅调用 API 不代表已开启消费归因或分成。

## 升级须知

旧版直接写数据库的方式已改为准备 RIS，必须完成 Zotero 原生导入。移除 `replace`，更新或合并现有条目使用 Zotero 自带操作。默认 `skip` 按 DOI/arXiv 归一化查重，忽略回收站条目，同一 arXiv 不同版本算一篇；不会覆盖已有 PDF，也无法识别缺少编号的重复记录或自动合并正式版/预印本。`new_copy` 用于明确需要另一份副本的情况。

查重覆盖本地各文献库，遇到群组库匹配需核对是否还应导入个人库；数据库不存在时只检查批内重复，已有数据库不可读则停止。`--collection` 只记录目标，原生导入后需选择实际分类。如果本批没有可准备的记录，结果 `ris` 为 null，旧输出保留但不应再次导入。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

GitHub CI 使用 Python 3.10 和 3.13。覆盖版本解析、PDF 版本选择、原生 RIS、只读查重、部分失败和可选 API 请求；接口测试使用模拟响应，不代表已验证真实计费或分成。范围为期刊、会议论文和预印本，不包括书籍与学位论文。PDF 签名检查只排除明显 HTML，仍需打开核验。`assets/` 原流程图展示旧版，当前以本说明为准。

[Skill 使用指引](SKILL.md) · [示例](examples.md) · [参考](reference.md) · [MIT 协议](LICENSE)
