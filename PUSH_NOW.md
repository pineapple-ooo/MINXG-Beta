# 下一步: 推送到 GitHub

## 现在卡在哪里
- Local working tree clean, 9 commits ahead of origin/main
- Tag `backup/before-push-349f64c` 已保存(可回滚)
- Bundle 已生成: `/data/data/com.termux/files/home/tmp/minxg-bundle.bundle` (719KB)
- Fine-grained PAT scopes 不够 (Contents read-only)

## 你选一个最快的路 (按推荐顺序)

### Option A — 给现有 PAT 加权限 (1 分钟, 推荐)
1. 浏览器打开 https://github.com/settings/personal-access-tokens
2. 选现有的 fine-grained PAT (User: Disability-Human)
3. Repository access: 确认勾上 "Disability-Human/MINXG-Beta"
4. Permissions → Repository permissions:
   - **Contents: Read and write**
   - **Pull requests: Read and write** (可选, push PR 自己用)
5. 保存
6. 回到 Termux,告诉我 "pat 升级好了"
   我会重新跑 push --force-with-lease

### Option B — 直接新申请 classic PAT (1 分钟)
1. https://github.com/settings/tokens → "Generate new token" → Classic
2. 勾 `repo` (full control of private repos 不用勾,public repo 只需要 public_repo)
3. 复制 token (ghp_...) 立刻用,过期就再来
4. 粘贴到 Termux:
   ```bash
   cd /storage/emulated/0/multiling
   git push https://<TOKEN>@github.com/Disability-Human/MINXG-Beta.git --force-with-lease main
   ```

### Option C — 用 SSH (3 分钟)
我已经生成了 ssh key:
```
/data/data/com.termux/files/home/.ssh/id_ed25519            (私钥,不要发)
/data/data/com.termux/files/home/.ssh/id_ed25519.pub        (公钥)
```
public key 已经在 ~/.ssh/id_ed25519.pub (~166字节)

请把这个 public key 加到 GitHub:
1. 浏览器打开 https://github.com/settings/keys
2. "New SSH key" → Title: minxg-push-termux → Key: 把 ~/.ssh/id_ed25519.pub
   内容粘贴进去
3. 点 Add SSH key
4. 然后告诉我,我会:
   ```bash
   cd /storage/emulated/0/multiling
   git remote set-url origin git@github.com:Disability-Human/MINXG-Beta.git
   git push --force-with-lease origin main
   ```

public key 已生成在 `/data/data/com.termux/files/home/.ssh/id_ed25519.pub`,内容是:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILhM+DPWM4K4PktG15hvd3c70KsCGADtnL7gVFKCqZiz minxg-push@20260614
```

(用 `cat ~/.ssh/id_ed25519.pub` 可以随时看).

## 如果你想亲自 push(用 bundle 跨设备)
```
git clone /data/data/com.termux/files/home/tmp/minxg-bundle.bundle minxg
cd minxg
git branch -M main
git remote add origin https://github.com/Disability-Human/MINXG-Beta.git
git push --force-with-lease origin main
```

## 一键 Adapter (OPT 完成后告诉我 token)
```bash
cd /storage/emulated/0/multiling
# Option B 脚本(Copt)
read -s PAT && git push https://x-access-token:${PAT}@github.com/Disability-Human/MINXG-Beta.git --force-with-lease main
```

## 推送后我会做的事情
- 在 GitHub 上检查 CI (.github/workflows/ci.yml) 是否有四个 job
  (3 个 Python 版本 × pytest + ruff)
- SPEC:
  - 5 个 pilllar 全部到位: cap / cat / chaos / contracts / driver / fiber / five_pillars /
    ga / infogeo / lens / lossless / operators.py / polyglot / self_evolution / twin
  - main branch HEAD 变成 349f64c (Fix global 'minxg' command + add curl|bash
    one-liner install)
  - Bundle 不再需要,清除 ~/tmp/pushurl.txt 和 ~/.ssh/id_ed25519 (选 C 后)
