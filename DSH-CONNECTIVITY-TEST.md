# DSH(mobile) 连接测试

这个文件由 **DeepSeek Harness（手机版）** 通过 GitHub Contents API 提交，
用于验证「建分支 → 提交文件 → 开 PR」这条完整写入链路。

| 步骤 | API |
|---|---|
| 建分支 | `POST /repos/{owner}/{repo}/git/refs` |
| 提交文件 | `PUT /repos/{owner}/{repo}/contents/{path}` |
| 开 PR | `POST /repos/{owner}/{repo}/pulls` |

**用途**：一次性连通性验证，**可以连同本分支一起删除**。

清理方式：关闭对应的 PR 后，GitHub 会提示 *Delete branch*；或到仓库 Branches 页面手动删除。
