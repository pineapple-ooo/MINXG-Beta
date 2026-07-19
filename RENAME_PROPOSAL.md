# MINXG 重命名方案

## 当前问题

**MINXG** 这个名字：
- ❌ 不好发音（min-xg? min-ex-gee?）
- ❌ 没有明确含义
- ❌ 搜索时容易被淹没
- ❌ README里"七根数学支柱"太学术

## 2026年GitHub爆款项目命名规律

| 项目名 | Stars | 命名特点 |
|--------|-------|----------|
| FastMCP | 26k+ | 快+协议名 |
| OpenClaw | 210k+ | Open+动物名 |
| ponytail | 84k+ | 日常词汇 |
| nanobot | 45k+ | nano+bot |
| graphify | 88k+ | graph+ify |

**规律**：
1. 2-3个音节，好发音
2. 包含功能关键词（MCP, bot, graph）
3. 容易搜索（不与其他词冲突）
4. 有记忆点

## 建议新名字

### 方案A：蹭MCP热点（推荐）

**名字**：`minxg-mcp` 或 `mcp-workers`

**理由**：
- MCP是2026年GitHub最火的关键词
- 直接表明用途
- 搜索MCP相关内容时会出现在结果里

**实施**：
- GitHub仓库名改为 `minxg-mcp`
- PyPI包名保持 `minxg-beta`（已有下载量）
- README标题：`MINXG MCP — Connect Claude to 70+ AI Workers`

### 方案B：功能描述型

**名字**：`ai-toolkit` 或 `agent-tools`

**理由**：
- 清晰描述功能
- 容易搜索
- 国际化

**实施**：
- GitHub仓库名改为 `ai-toolkit`
- 副标题：`70+ AI Workers for Claude Code, Cursor, and ChatGPT`

### 方案C：品牌重塑型

**名字**：`workerforge` 或 `toolforge`

**理由**：
- 有品牌感
- forge暗示"锻造工具"
- 容易记住

**实施**：
- GitHub仓库名改为 `workerforge`
- 口号：`Forge Your AI Workforce`

## 我的推荐：方案A

**原因**：
1. MCP是2026年最火的AI基础设施关键词
2. 所有主流AI客户端都支持MCP
3. 搜索"Python MCP server"时会出现
4. 不需要完全抛弃MINXG品牌

## 实施步骤

1. **GitHub仓库重命名**
   ```
   MINXG-Beta → minxg-mcp
   ```

2. **README重写**（已完成）
   - 突出MCP关键词
   - 短+清晰价值主张

3. **添加MCP Server**（已完成）
   - `minxg/mcp_server.py`

4. **创建Claude Code Skills**（已完成）
   - `.claude/skills/minxg/`

5. **发布到Product Hunt + Hacker News**
   - 标题：`MINXG MCP — Connect Claude Code to 70+ AI Workers`
   - 标签：mcp, claude-code, ai-agents, python

6. **提交到awesome-mcp-servers**
   - 90k+ stars的列表
   - 免费流量

## 预期效果

| 指标 | 当前 | 目标（3个月） |
|------|------|---------------|
| GitHub Stars | ~50 | 1,000+ |
| PyPI Downloads | ~500/月 | 5,000+/月 |
| MCP Servers列表 | 0 | 3+ |

## 风险

- 改名可能丢失现有搜索权重
- 需要重新建立品牌认知
- PyPI包名不能改（已有下载量）

## 缓解措施

- 保持PyPI包名 `minxg-beta`
- GitHub仓库设置重定向
- README保留旧名字引用
