# Supadata「Publish a template or repo」奖励发布指南

这个奖励和「写教程」不同：重点是 **GitHub 仓库要有真实使用 Supadata SDK 的可运行开源应用**。

## 项目名称

`supadata-research-vault`

建议未来仓库地址（创建后才会生效）：

https://github.com/hubao201198/supadata-research-vault

## 这个项目做了什么

- 真正通过 `from supadata import Supadata` 实例化官方 SDK；
- 获取字幕，支持已完成同步结果和 `get_job_status()` 异步轮询；
- 保留文字、语言和毫秒级时间戳；
- SQLite FTS5 本地全文检索；
- 批量 URL 导入、失败不中断整个批次、重复导入更新；
- 导出 Markdown 或 JSON；
- 自带零积分、无需 API Key 的**明确标注为模拟数据**的本地演示；
- 18 项自动化离线测试和 GitHub Actions；
- README 内已包含专属推广链接：https://supadata.ai/r/9YW9BZ05，并说明推广关系。

## 具体操作

1. 打开 https://github.com/new，新建 Public 仓库：`supadata-research-vault`。
2. 不要勾选 Create README / gitignore / license，保持仓库空白。
3. 创建成功后，在 ChatGPT 对话中回复「新仓库创建好了」，我可以直接通过已连接 GitHub 将全部文件提交进去。也可以自行解压 ZIP、上传**全部文件和文件夹**，不能只上传 README.md。
4. 打开仓库的 Code 页面，检查 `research_vault/sdk_client.py`、`requirements.txt`、`tests/`、`.github/workflows/tests.yml` 是否存在。
5. 在 Actions 查看离线测试情况；在自己的机器尝试一次真实调用，并将测试结论写入 README（注意不要暴露 API Key）。
6. 将仓库公开地址填入 Supadata **Publish a template or repo -> Repository URL**，点击 Verify and claim。

## 运行

```bash
python3 -m research_vault demo
python3 -m research_vault search "research"
python3 -m unittest discover -s tests -v

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export SUPADATA_API_KEY="YOUR_API_KEY"
python -m research_vault add "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --mode native
```

## 重要说明

- 文件已通过 18 项离线测试，**尚未使用实际 API Key 调用 Supadata 线上接口**；真实运行需你自己提供有效 Key。
- `--mode native` 默认只使用已有字幕，`auto`/`generate` 可能消耗额外额度。
- `requirements.txt`/`pyproject.toml` 固定到含 `get_job_status` 的 Supadata 官方 GitHub SDK 1.7.0 提交，因为 PyPI 最新正式版与文档有差异。
- 只有在仓库公开可访问、代码实际存在并且功能符合活动规则时，才可能通过审核。具体是否接受以 Supadata 结果为准。
