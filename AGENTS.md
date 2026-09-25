# Repository Guidelines

## 项目结构

- `src/`：Python 源码，包括文件发现、文件内证据定位、基准测试与评估模块，目前主要采用扁平布局。
- `tests/`：单元测试与回归测试。
- `fixtures/`：仓库样本、固定研究输入与定价快照。
- `docs/domains/`：文件发现与证据定位的领域说明。
- `docs/research/`：研究过程与结论。
- `docs/experiments/`：实验协议与结果。
- `docs/pilots/`：早期探索记录。
- `.github/workflows/`：GitHub Actions 工作流。
- `README.md`、`ROADMAP.md`：项目介绍与路线图。
- `docs/project-structure.md`：当前结构与目标结构说明。

## 约束

- 所有运行（包括测试、实验、基准测试和脚本执行）都必须通过 GitHub Actions Workflow 完成，不得在本地运行。
- 每次研究都必须生成研究报告，保存到 `docs/research/`，记录研究目标、方法、结果与结论，并关联对应的 Workflow 运行及产物。
