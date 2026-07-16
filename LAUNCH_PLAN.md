# MINXG MCP 发布计划

## 发布前检查清单

### 代码准备

- [x] MCP Server实现 (`minxg/mcp_server.py`)
- [x] Claude Code Skills (`.claude/skills/minxg/`)
- [x] 新README (`README_MCP.md`)
- [x] 重命名方案 (`RENAME_PROPOSAL.md`)
- [ ] 测试MCP服务器启动
- [ ] 验证工具列表
- [ ] 添加单元测试

### 文档准备

- [ ] 更新README.md（替换为MCP版本）
- [ ] 添加MCP配置示例
- [ ] 创建CHANGELOG条目
- [ ] 更新pyproject.toml关键词

### 发布渠道

#### 1. GitHub

- [ ] 仓库重命名：`MINXG-Beta` → `minxg-mcp`
- [ ] 更新仓库描述：`MINXG MCP — Connect Claude Code to 70+ AI Workers`
- [ ] 添加Topics：`mcp`, `claude-code`, `ai-agents`, `python`, `worker`
- [ ] 创建Release：`v0.19.0-mcp`

#### 2. Product Hunt

- [ ] 准备截图/GIF
- [ ] 写Tagline：`Connect Claude Code to 70+ AI Workers via MCP`
- [ ] 准备First Comment
- [ ] 选择发布日期（周二-周四）

#### 3. Hacker News

- [ ] 标题：`Show HN: MINXG MCP — 70+ AI Workers for Claude Code`
- [ ] 准备技术细节
- [ ] 准备好回复问题

#### 4. Reddit

- [ ] r/selfhosted
- [ ] r/opensource
- [ ] r/claude
- [ ] r/LocalLLaMA

#### 5. MCP目录

- [ ] awesome-mcp-servers (90k+ stars)
- [ ] glama.ai/mcp/servers
- [ ] mcpso.ai
- [ ] pulsemcp.com

### 发布后

- [ ] 监控GitHub Stars增速
- [ ] 回复所有Issues和PRs
- [ ] 收集用户反馈
- [ ] 准备v0.19.1修复

## 时间线

| 日期 | 任务 |
|------|------|
| Day 1 | 代码准备完成，内部测试 |
| Day 2 | GitHub重命名，Release发布 |
| Day 3 | Product Hunt发布（周二） |
| Day 4 | Hacker News Show HN |
| Day 5 | Reddit发布 |
| Day 6-7 | 回复反馈，修复bug |
| Week 2 | 提交MCP目录，持续更新 |

## 成功指标

| 指标 | 目标 | 时间 |
|------|------|------|
| GitHub Stars | 1,000+ | 30天 |
| PyPI Downloads | 5,000+/月 | 30天 |
| MCP目录收录 | 3+ | 7天 |
| Issues/PRs | 10+ | 30天 |

## 风险缓解

| 风险 | 缓解措施 |
|------|----------|
| 改名丢失SEO | GitHub自动重定向 |
| MCP服务器bug | 快速发布v0.19.1 |
| 发布后无关注 | 多平台同时发布 |
| 负面反馈 | 快速响应，透明沟通 |

## 预算

| 项目 | 成本 |
|------|------|
| Product Hunt | $0 (免费) |
| Hacker News | $0 (免费) |
| Reddit | $0 (免费) |
| MCP目录 | $0 (免费) |
| **总计** | **$0** |

## 下一步

1. 测试MCP服务器
2. 更新主README
3. 执行GitHub重命名
4. 准备Product Hunt发布
