# crux

`crux` 是一个 LLM-facing 的统一入口——一层薄 umbrella,把 verb 用 git 式 dispatch 路由到各独立工具:

    crux recall "<问题>"   # KB 召回(转发到 Memex)
    crux pm <args>         # 工作状态(转发到 Docket)
    crux surface           # 能力面:crux verbs + 本机工具目录
    crux stats             # 本地用量统计

它本身几乎不做事,只做路由 + 能力面 surface,把高频入口收成一个好记的命令。各 verb 的目标工具用 `CRUX_*` 环境变量配置(见 `crux --help`)。

## 安装

从 [GitHub Releases](https://github.com/the-orrery/crux/releases) 下载
`crux-<os>-<arch>` 并按 `SHA256SUMS` 校验。二进制不依赖 Python、`uv` 或本地
源码仓；被路由的 `memex`、`docket` 等命令仍需在 PATH，亦可用显式 `CRUX_*_BIN`
覆盖。该边界沿用 PR #12 的 installed-binary dispatch 设计。

当前发布 macOS arm64 和 Linux x86_64（Ubuntu 22.04 基线）。

## 开发

    uv sync
    uv run poe check
    ./scripts/build-release.sh
