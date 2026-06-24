# PUSH.md — 上线最后一步

项目已经准备好。`git init` 在本地完成,第一次 commit `8a82205`
已经落地,working tree 干净。

剩余两步都是**只能你来做的**(需要 GitHub 凭据)。

## 1) 在 GitHub 上创建空仓库

```
浏览器打开:  https://github.com/new
Repository name:  minxg
Owner:            minxg-source   (或你自己的 GitHub 用户名)
Visibility:       Public
Initialize:       不要勾 README / LICENSE / .gitignore — 都空着
```

创建后你会进到一个 "Quick setup" 页面。**记下 HTTPS 那个 URL**,
大概是 `https://github.com/minxg-source/minxg.git`(如果用户名不同
就替换)。

## 2) push

项目里已经预置了 remote,你只需要 push:

```bash
cd /storage/emulated/0/multiling

# 如果 remote 用户名不是 minxg-source,先改:
git remote set-url origin https://github.com/<你的用户名>/minxg.git

# push
git push -u origin main
```

认证选 **HTTPS + Personal Access Token**(不是密码)。Token 在
https://github.com/settings/tokens 申请,勾 `repo` 即可。Termux 的
git helper 会弹窗口让你粘贴。

## 3) 验证 CI

push 完成后到 https://github.com/<你的用户名>/minxg/actions 看
GitHub Actions 是否跑过 6 个 job(3 个测试×3 个 Python 版本 + ruff)。

最终确认:
-  [ ] 仓库地址在 README 顶部 badge 正确显示
-  [ ] CI 绿勾出现,把 badge 从 404 状态变成绿色
-  [ ] 在 README 顶部能看见 "Tests 66 passed" / "Pillars 6" / "CI passing"

## 已知不需要再做但记得

-  `pip install -e .[dev]` 在 Termux 第一次跑需要 30~60s;GitHub
   Actions 跑得更快(用了 cache)。
-  CI 失败常见原因(任一发生我帮你排查):
    - `OPERATOR_REGISTRY.total_operators != 376` — 加了新算子或漏注册
    - `pytest` 在 3.11/3.13 上 syntax error — 用了 3.12-only 语法
    - 网络问题从 setup-python 里 pip install 失败 — 重跑即可

完。
