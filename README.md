# crux

`crux` 是一个 LLM-facing 的统一入口——一层薄 umbrella,把 verb 用 git 式 dispatch 路由到各独立工具:

    crux recall "<问题>"   # KB 召回(转发到 Memex)
    crux pm <args>         # 工作状态(转发到 Docket)
    crux surface           # 能力面:crux verbs + 本机工具目录
    crux stats             # 本地用量统计

它本身几乎不做事,只做路由 + 能力面 surface,把高频入口收成一个好记的命令。各 verb 的目标工具用 `CRUX_*` 环境变量配置(见 `crux --help`)。

## 开发

    uv sync
    uv run poe check
