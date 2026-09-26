# Repository Guidelines

## 项目结构

- `src/`：文件发现、证据定位、基准和评估代码。
- `tests/`：单元测试与回归测试。
- `fixtures/`：固定输入、仓库样本和可复用参考数据。
- `research/`：当前及后续实验记录；一个实验对应一个独立目录。
- `docs/research/`：迁移前的历史研究记录，只作历史索引。
- `.github/workflows/`：测试、实验、汇总和产物上传入口。
- `README.md`：项目入口，并按时间追踪实验进展。

## 约束

- 实验直接在 `main` 上开发、提交和运行，不创建实验分支或实验工作树。
- 所有项目运行，包括测试、实验、基准测试和项目脚本，只能通过 GitHub Actions Workflow 执行；本地只允许编辑文件、检查 Git 状态和读取已有数据。
- 开始实验前，在 `research/YYYY-MM-DD-<experiment-name>/` 建立目录，并冻结任务、仓库 revision、模型、参数、对照组、指标和停止条件。
- 每个实验目录必须包含 `README.md`，且明确包含“实验目标”“实验方案”“实验过程”“实验数据”“实验结果”五个二级标题。失败、中止或无显著结果也必须完整记录。
- `data/` 保存可提交的固定输入、汇总和关键结果；不得只在正文中手工抄写指标。大体积原始结果保存在 GitHub Actions artifacts。
- `workflow/metadata.json` 必须记录 Workflow URL、run ID、commit SHA、状态、Jobs 和产物清单。报告必须链接该 Workflow，并说明产物名称、用途和保留期。
- 实验流程为：定义并预注册方案 → 提交 `main` → 由 Workflow 运行 → 检查 Jobs 与 artifacts → 固化数据和结论 → 更新实验目录、`research/README.md` 与根 `README.md` → 再由 Workflow 验证最终提交。
- 不得把候选数硬上限当作算法优化；应报告召回、文件打分数、目录判断数、tokens、调用次数、延迟和失败案例，并从算法上降低规模。
