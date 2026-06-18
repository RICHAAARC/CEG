# CEG paper_workflow 独立 Colab 会话运行契约

## 1. 总原则

CEG 的 `paper_workflow` 必须满足以下运行原则:

1. 每个 Notebook 都假设自己运行在一个全新的 Colab 会话中。
2. Notebook 不得依赖上一个 Colab 会话的 `/content` 目录、Python 进程、内存对象或本地临时文件。
3. 跨 Notebook 的唯一稳定交接方式是 Google Drive 中的阶段归档 zip 与 manifest。
4. GitHub 仓库是代码和仓库内置 prompt plan 的来源。
5. Google Drive 是阶段结果、归档包、外部模型权重和最终论文结果包的来源或落盘位置。
6. Notebook 只负责环境准备和调度仓库脚本, 不直接实现 CEG 主方法、水印算法、检测算法、指标算法或论文表格生成逻辑。

该设计参考了 `CEG-WM` 中已经跑通的冷启动思想: 每个 PW Notebook 都能独立拉取仓库、准备环境、读取 Drive 阶段包、执行当前阶段、再把结果打包回 Drive。

## 2. 阶段总览

| Notebook | 阶段职责 | 是否读取前序阶段 | 是否写 Drive 阶段归档 | 是否支持正式论文结果声明 |
|---|---|---:|---:|---:|
| `colab_pilot_image_generation_outputs.ipynb` | 从 prompt 生成 clean / watermarked 图像和 image manifests | 否 | 是 | 只支持图像产物合规声明 |
| `colab_external_baseline_outputs.ipynb` | 运行外部 baseline command plan | 是, 读取图像生成归档 | 是 | 需要 baseline evidence |
| `colab_paper_results_pipeline.ipynb` | attack、detection、fixed-FPR、表格图表和结果包 | 是, 必须读取图像生成归档 | 是 | 是, 主论文结果包入口 |
| `colab_end_to_end_paper_pipeline.ipynb` | 单会话串联图像生成和结果包 | 否 | 是 | 是, 适合 probe 或单会话自动化 |
| `colab_ceg_cold_start.ipynb` | dry-run 或 provided results 重建 | 否 | 是 | 默认 dry-run 不支持正式声明 |

## 3. 分阶段正式流程

推荐正式运行采用分阶段 Notebook, 因为长时间 GPU 任务容易被 Colab 中断, 分阶段归档可以最大限度保存已完成结果。

### 3.1 图像生成阶段

入口:

```text
paper_workflow/colab_pilot_image_generation_outputs.ipynb
```

读取:

```text
GitHub: RICHAAARC/CEG
仓库: prompts/prompt_plans/{profile}_prompt_plan.json
Drive: /content/drive/MyDrive/Models/inspyrenet/ckpt_base.pth
Colab secret 或环境变量: HF_TOKEN, CEG_ATTESTATION_KEY
```

本地运行目录:

```text
/content/ceg_runtime/{run_id}/inputs/images
```

核心产出:

```text
clean/
watermarked/
semantic_masks/
watermark_metadata/
image_pairs.json
image_manifests/image_generation_manifest.json
image_manifests/image_pair_manifest.json
real_image_generation_backend_manifest.json
pilot_image_generation_output_acceptance_report.json
```

Drive 归档:

```text
/content/drive/MyDrive/CEG/archives/image_generation_outputs/{run_id}.zip
/content/drive/MyDrive/CEG/archives/image_generation_outputs/{run_id}_manifest.json
```

下游读取者:

```text
colab_paper_results_pipeline.ipynb
colab_external_baseline_outputs.ipynb
```

### 3.2 外部 baseline 阶段

入口:

```text
paper_workflow/colab_external_baseline_outputs.ipynb
```

读取:

```text
Drive 图像生成归档 zip
用户提供或脚本物化的 baseline_plan.json
```

产出:

```text
external_baselines/baseline_observations.json
external_baselines/baseline_execution_manifest.json
```

Drive 归档:

```text
/content/drive/MyDrive/CEG/archives/external_baseline_outputs/{run_id}.zip
/content/drive/MyDrive/CEG/archives/external_baseline_outputs/{run_id}_manifest.json
```

说明:

外部 baseline 不应实现 CEG 主方法, 只负责运行第三方 baseline 并把结果统一成 CEG 可读取的 `baseline_observations.json`。

### 3.3 论文结果包阶段

入口:

```text
paper_workflow/colab_paper_results_pipeline.ipynb
```

必须读取:

```text
/content/drive/MyDrive/CEG/archives/image_generation_outputs/{image_generation_run_id}.zip
```

可选读取:

```text
/content/drive/MyDrive/CEG/archives/external_baseline_outputs/{baseline_run_id}.zip
```

本地恢复:

```text
/content/ceg_runtime/{run_id}/inputs/images
/content/ceg_runtime/{run_id}/external_baselines
```

核心产出:

```text
paper_results_pipeline/attack_outputs
paper_results_pipeline/detection_outputs/detection_events.json
paper_results_pipeline/metric_outputs/quality_metric_rows.json
paper_results_pipeline/calibrated_paper_results_package/paper_results_package
paper_results_pipeline/colab_paper_results_pipeline_manifest.json
```

Drive 归档:

```text
/content/drive/MyDrive/CEG/package_archives/paper_results_package_*.zip
/content/drive/MyDrive/CEG/result_inventories/drive_result_inventory_{run_id}.json
```

该阶段是论文主结果入口, 负责产出或重建:

- `TPR@FPR=0.01`
- `TPR@FPR=0.001`
- attack robustness 表
- baseline comparison 表
- quality metrics 表
- 示例图像索引
- 论文结果包 manifest

## 4. 单会话端到端流程

入口:

```text
paper_workflow/colab_end_to_end_paper_pipeline.ipynb
```

该 Notebook 在同一个 Colab 会话中串联图像生成和论文结果包生成。它适合:

1. 小规模 `paper_main_probe` smoke / probe。
2. Colab 会话足够稳定时的一次性 pilot。
3. 调试完整链路是否可运行。

对于 `paper_main_full`, 推荐使用分阶段流程, 避免 Colab 会话中断导致所有中间结果丢失。

## 5. 与 CEG-WM 的对齐点

CEG 的重构目标不是复制 CEG-WM 的复杂门禁, 而是学习其成熟运行机制:

1. 每个 Notebook 独立冷启动。
2. 每个阶段显式读取 Drive 上一个阶段归档。
3. 每个阶段完成后写回 Drive 归档和 manifest。
4. 模型缓存、InSPyReNet 权重、环境变量和日志诊断由 Colab helper 管理。
5. 方法逻辑保留在 `main/`、`experiments/` 和 `scripts/` 中。

## 6. 当前仍需严格遵守的边界

1. 不允许 Notebook 直接手写正式 records、tables、figures 或 reports。
2. 不允许 CEG 调用 CEG-WM 仓库代码。
3. 不允许把 CEG-WM 的复杂门禁直接搬到 CEG 主方法中。
4. 不允许把 Google Drive 当作代码运行目录; Drive 只用于输入归档、输出归档和模型权重。
5. 不允许把 HF token 或 attestation secret 写入 manifest、日志或 zip。

## 7. 机器可读契约

机器可读版本保存在:

```text
configs/paper_workflow_notebook_contract.json
```

后续测试和 Notebook 审计应优先读取该文件, 而不是依赖散落在 README 中的自然语言说明。
