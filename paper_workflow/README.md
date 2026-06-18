# Paper Workflow

此目录保存论文相关 Notebook workflow 入口和执行环境封装。Notebook 只能调度 repository modules, 不得成为唯一正式实现。

## Colab 冷启动入口

`paper_workflow/colab_ceg_cold_start.ipynb` 用于本地没有 GPU 的场景。推荐流程如下:

1. 在 Google Colab 中打开该 Notebook。
2. 在配置区填写 `REPO_URL` 或把项目上传到 `/content/CEG`。`REPO_BRANCH` 默认留空, 表示使用远端默认分支; 只有需要固定复现实验所在分支时才填写, 避免 `main` / `master` 分支名不一致导致冷启动 clone 失败。
3. 结果默认落盘到 Google Drive 的 `/content/drive/MyDrive/CEG`, 该目录会按结果类型划分 `inputs/`、`experiment_matrix/`、`paper_outputs/`、`paper_results_package/`、`colab_run_bundle/`、`provided_results/`、`external_baselines/`、`external_metrics/`、`acceptance/` 和 `archives/`。
4. 若只验证端到端链路, 保持 `USE_DRY_RUN_INPUTS = True`。
5. 若运行真实实验结果, 将 `USE_DRY_RUN_INPUTS = False`。可以直接填写 `EVENTS_PATH` 和 `THRESHOLDS_PATH`; 也可以填写 `SAMPLE_MANIFEST_PATH` 和 `THRESHOLDS_PATH`, 由仓库脚本生成协议事件。
6. 若需要把实验矩阵覆盖率作为正式门禁, 设置 `REQUIRE_EXPERIMENT_COVERAGE = True`。dry-run 只验证链路, 不覆盖完整论文矩阵, 因此不建议开启该门禁。
7. 执行全部 cell 后, Notebook 会调用 repository scripts 生成:
   - `experiment_matrix/`
   - `paper_outputs/`
   - `paper_results_package/`
   - `colab_run_bundle/`
   - `archives/ceg_colab_run_bundle.zip`
   - `archives/colab_bundle_archive_manifest.json`
   - `colab_output_layout_manifest.json`
   - `colab_formal_input_contract.json`
   - `inputs/formal_input_templates_manifest.json`
   - `colab_formal_runbook.md`
   - `colab_paper_result_index.json`
   - `colab_formal_result_gap_report.json`

该 Notebook 不直接写正式 records、tables、figures 或 reports; 它通过 `paper_workflow/notebook_utils/protocol_entrypoint.py` 调用仓库内的正式脚本和模块。`colab_formal_input_contract.json` 会随 workspace 与 bundle 一起落盘, 用于说明正式运行所需的 events、thresholds、sample manifest、baseline observations、metric rows、image pairs 和第三方命令接口。`inputs/formal_input_templates_manifest.json` 会指向 `inputs/formal_input_templates/` 下的可填写模板, 这些模板只用于准备真实输入, 不作为正式实验结果或论文证据。`colab_formal_runbook.md` 会把输入准备、模板路径、正式清单状态、缺口报告和验收命令汇总为人类可读说明书。


## Colab 正式输入模板

冷启动环境会写出 `inputs/formal_input_templates/` 目录, 其中包含以下可填写模板:

```text
events_template.json
thresholds_template.json
sample_manifest_template.json
baseline_observations_template.json
metric_rows_template.json
image_pairs_template.json
```

这些文件的用途是降低正式运行前整理输入的成本。使用时应复制模板到 Notebook 配置区指定的真实输入路径, 再用真实实验值替换示例值。模板本身不会被 `build_paper_outputs.py` 当作正式 records 消费, 也不会支持任何论文 claim。正式运行仍必须通过 `colab_formal_run_checklist.json`、`paper_result_evidence_report.json` 和 `run_colab_acceptance_checks.py` 的严格验收。

## 阈值校准

如果真实实验还没有准备 `thresholds.json`, 可以设置 `CALIBRATE_THRESHOLDS = True`, 并提供包含 `calibration` split 的 `SAMPLE_MANIFEST_PATH`。冷启动链路会先调用 `scripts/calibrate_thresholds_from_sample_manifest.py`, 根据 clean negative 的 `content_score_raw` 和 `THRESHOLD_TARGET_FPR` 生成:

```text
threshold_calibration/thresholds.json
threshold_calibration/threshold_calibration_report.json
```

该校准步骤只使用样本清单中已有分数, 不运行模型, 不手工拼接正式结果。生成的 `thresholds.json` 会作为后续协议事件构建和论文结果重建的显式输入。

## 样本清单到协议事件

如果真实实验还没有整理成 `events.json`, 可以提供 `SAMPLE_MANIFEST_PATH`。样本清单支持 JSON、JSONL 或 CSV, 每行至少包含:

```text
event_id
split
sample_role
attack_family
attack_condition
is_watermarked
content_score_raw
attestation_score
```

可选字段包括 `content_score_aligned`、几何恢复字段、标准水印指标字段、`reference_path` 和 `watermarked_path`。当 `COMPUTE_BASIC_IMAGE_METRICS = True` 且样本清单包含图像配对路径时, Colab 链路会调用 `scripts/compute_image_quality_metrics.py` 生成轻量 `psnr` 和 `ssim` 指标行。LPIPS、FID 和 CLIP score 仍建议通过外部 metric plan 在 GPU 环境计算。

## 外部 baseline 与高级指标计划

Colab Notebook 支持两种真实实验输入方式:

1. 已经有 `baseline_observations.json` 和 `metric_rows.json` 时, 直接填写 `BASELINE_OBSERVATIONS_PATH` 和 `METRIC_ROWS_PATH`。
2. 需要在 Colab GPU 环境运行第三方 baseline 或 LPIPS/FID/CLIP score 时, 设置 `RUN_EXTERNAL_PLANS = True`, 并填写 `BASELINE_ROOT`、`METRIC_ROOT` 以及图像配对或图像目录路径。Notebook 会通过仓库脚本物化命令计划, 再调用 `run_baseline_plan.py` 和 `run_metric_plan.py` 汇总输出。

正式输入契约会写入 `colab_formal_input_contract.json`: 其中 `input_files` 列出 `events`、`thresholds`、`sample_manifest`、`baseline_observations`、`metric_rows` 和 `image_pairs` 的推荐路径、格式与最小字段; `third_party_command_interfaces` 列出第三方 baseline 和高级指标脚本需要输出的统一字段; `formal_acceptance_requirements` 列出正式验收必须满足的非 dry-run、实验矩阵覆盖、来源模式证据、论文结果索引生产追踪完整性、正式结果缺口报告 readiness 和严格 acceptance 条件。这里的来源模式证据分为两类: `provided_file` 依赖 `provided_result_files_manifest.json` 校验直接提供结果副本, `external_plan` 才依赖 `--require-external-command-results` 校验外部命令结果。

运行前建议先查看 `colab_environment_summary.json` 中的 `nvidia_smi` 和 `torch_cuda` 字段, 确认 Colab 已分配 GPU。正式运行清单也会写出 `gpu_readiness`: 当 `RUN_EXTERNAL_PLANS = True` 且 `USE_DRY_RUN_INPUTS = False` 时, 默认要求检测到 GPU, 否则会产生 `gpu_runtime_unavailable_for_external_plans` 阻断项。若第三方 baseline / metric 任务已确认只需要 CPU, 可将 `REQUIRE_GPU_FOR_EXTERNAL_PLANS = False` 作为显式放宽。

## 实验矩阵覆盖率报告

冷启动链路会先执行 `scripts/build_experiment_matrix.py`, 再把 `experiment_matrix.json` 传给 `scripts/build_paper_outputs.py`。最终结果包会包含 `artifacts/paper_experiment_coverage_report.json`。

该报告用于区分两种状态:

- `overall_decision = pass`: 当前 records 已覆盖所选 profile 下矩阵声明的 split、method、sample_role 和 attack_condition。
- `overall_decision = fail`: 当前 records 只能支持链路验证或部分实验, 还不能声称完整覆盖论文实验矩阵。

该覆盖率报告属于审计产物, 不会替代真实 GPU 实验或第三方 baseline 实现。


## Colab 正式运行说明书

`colab_formal_runbook.md` 会随 workspace 和 bundle 一起生成。该文件读取已经存在的输入契约、模板 manifest、正式运行清单、正式结果缺口报告、acceptance report 和 archive manifest, 然后给出以下信息:

- Drive 输出根目录和类型化子目录。
- 每类正式输入的推荐路径和必需字段。
- 可填写模板的位置。
- 当前正式运行清单和结果缺口状态。
- 可复跑的 bundle / evidence / acceptance 命令。

该 runbook 只用于操作说明和离线复核, 不生成 records、tables、figures 或 reports, 也不能替代 GPU 上的外部 baseline 和高级指标计算。

## 运行级 bundle

Notebook 最终下载的是 `archives/ceg_colab_run_bundle.zip`, 同时该文件会保留在 `/content/drive/MyDrive/CEG/archives/`。zip 内会包含 `archives/colab_bundle_archive_manifest.json` 的 `pre_archive_sidecar` 版本, 用于在下载包内部声明离线验收命令和预期归档文件名; Drive 外层同名 sidecar 会在 zip 写出后更新为 `post_archive_sidecar`, 并记录 `archive_sha256`。`colab_output_layout_manifest.json` 会记录各类结果目录、用途、存在状态和文件数量, 用于确认 Drive 根目录下的类型化落盘契约。`colab_formal_input_contract.json` 会声明正式输入文件、字段和第三方脚本接口, 便于下载后确认 Colab 正式运行是否具备可复现实验输入。`colab_paper_result_index.json` 会进一步把论文主表、标准水印指标、baseline / 消融对比表、图表规格、LaTeX / PDF / Markdown 报告和 Colab 交付件映射到具体路径, 并写出 `required_result_group_summary`、`required_result_group_failures` 等组级判定。对于标准水印指标、质量指标长表、baseline / 消融表、图表规格和报告等关键文件, 索引还会写出 `semantic_check`、`semantic_check_summary` 和 `semantic_check_failures`, 便于下载后按结果类型和内容结构复核“论文所需结果是否已经产出”。每个 `indexed_results` 条目还包含 `production_trace`, 用 `producer_steps`、`required_inputs` 和 `validation_gates` 显式说明该结果由哪些仓库脚本或模块生成、依赖哪些上游输入以及由哪些门禁验收; 顶层 `production_trace_summary` 用于确认所有 result_id 都具备可追溯生成链路。`colab_formal_result_gap_report.json` 会把当前运行距离正式论文结果声明仍缺少的证据显式列出, 例如 dry-run 输入、实验矩阵覆盖率未强制通过、论文结果索引生产追踪缺失、直接提供结果 manifest 缺失、外部 baseline / 高级指标命令结果缺失、GPU runtime 未就绪或严格 evidence / acceptance 未通过。该压缩包包含 `paper_results_package/` 以及 Colab 运行 provenance, 包括环境摘要、命令计划、输入清单、实验矩阵、阈值校准报告、样本转换 manifest、直接提供结果副本摘要、外部 baseline / metric 命令结果摘要等。`colab_run_bundle_validation.json` 会校验 bundle manifest 中的文件摘要、内嵌 archive sidecar 的 `pre_archive_sidecar` 阶段和离线验收命令, 以及内嵌论文结果包校验是否通过。cold-start pipeline 会在末端调用 `create_colab_bundle_archive(...)` 创建下载包, 并在 `archives/` 中写出 `colab_bundle_archive_manifest.json`; `colab_cold_start_summary.json` 也会记录 zip 路径、大小、SHA-256 和离线验收命令, 使自动化调用和 Notebook 展示使用同一份交付信息。该 manifest 会区分 `colab_acceptance_command` 和 `offline_acceptance_command`: 前者使用 Colab 会话内的绝对 zip 路径, 后者使用 `path/to/ceg_colab_run_bundle.zip` 占位路径, 便于下载 zip 和 sidecar manifest 后在同一目录复跑。离线验收命令会按当前运行模式补充 `--allow-dry-run`、`--allow-missing-experiment-coverage` 或 `--require-external-command-results`; 其中 `--require-external-command-results` 仅在 `RUN_EXTERNAL_PLANS=True` 的外部命令来源模式下出现, 避免下载后复核命令和实际运行来源不一致。

### 独立校验运行级 bundle

Colab 下载 `ceg_colab_run_bundle.zip` 后, 可以在本地或 CI 中复核 bundle manifest、文件摘要和内嵌论文结果包校验状态:

```powershell
python scripts/validate_colab_run_bundle.py --bundle path\to\ceg_colab_run_bundle.zip --out bundle_validation.json --require-pass
```

也可以直接校验解压后的目录:

```powershell
python scripts/validate_colab_run_bundle.py --bundle path\to\colab_run_bundle --require-pass
```

该 CLI 不重新生成正式 records、tables、figures 或 reports, 只复用仓库模块中的 bundle 校验逻辑读取已有运行证据。

### 正式结果证据完整性校验

`validate_paper_result_evidence.py` 在目标是 `colab_run_bundle/` 时, 还会读取 `colab_formal_run_checklist.json`。正式论文证据默认要求该清单 `overall_decision = pass` 且 `blocking_issue_count = 0`。`validate_colab_run_bundle.py` 还会检查 `colab_paper_result_index.json` 中的 `semantic_check_summary`、`semantic_check_failures` 和 `production_trace_summary`, 因此关键论文结果文件即使存在, 只要内容结构校验失败, 或缺少生成步骤与验收门禁追踪, 也不能通过运行级 bundle 验收。如果只是验证 dry-run 调试链路, 可以显式使用 `--allow-dry-run`; 此时清单失败会被记录为 dry-run 放宽证据, 但不能支持正式论文结果声明。

`--require-external-command-results` 只用于 `external_plan` 来源模式。启用后, 该门禁还会读取 `external_baselines/baseline_observations.json` 与 `external_metrics/metric_rows.json`。外部命令返回码为 0 只是必要条件; baseline observation 必须包含 `event_id`、`baseline_id`、`score`、`threshold`, 高级指标行必须包含 `event_id` 且至少包含 `lpips`、`fid` 或 `clip_score` 之一。这样可以防止第三方脚本空跑或只生成基础 PSNR / SSIM 文件时被误判为正式高级指标结果。若来源模式是 `provided_file`, 严格验收不应强制该参数, 而是校验 `provided_results/provided_result_files_manifest.json` 及其副本摘要。


`paper_readiness_report.json` 只能证明结果产物链路完整, 不能单独证明这些结果来自正式 GPU 实验。正式论文结果验收建议在 Colab bundle 下载后按来源模式继续运行。

外部命令来源模式的正式验收命令为:

```powershell
python scripts/validate_paper_result_evidence.py --target path\to\colab_run_bundle --require-external-command-results --require-pass
```

直接提供结果文件模式的正式验收命令为:

```powershell
python scripts/validate_paper_result_evidence.py --target path\to\colab_run_bundle --require-pass
```

上述两类校验默认都会拒绝 dry-run 标记, 并要求实验矩阵覆盖率通过。若只是在本地验证链路, 可以显式放宽:

```powershell
python scripts/validate_paper_result_evidence.py --target path\to\paper_outputs --allow-dry-run --allow-missing-experiment-coverage
```

因此, `validate_paper_result_evidence.py` 属于正式结果验收门禁, 不是新的指标生成器; 它只读取已有 records、artifacts、manifest 和 Colab 命令 provenance。

## Colab 正式实验运行清单

### 正式输入源结构预检

正式运行清单会在启动长耗时实验前生成 `formal_input_source_preflight`。该预检只读取轻量输入文件, 不运行模型, 不生成正式 records。它会检查:

- `events.json` 是否为非空 JSON / JSONL / CSV 行集合, 且每行包含 `event_id`、`method_name`、`split`、`sample_role`、`attack_family`、`attack_condition`、`is_watermarked` 和对象形式的 `payload`。
- `thresholds.json` 是否为非空 method name 到阈值的映射。
- `sample_manifest` 是否包含正式样本清单必需字段, 便于后续转换为协议事件。
- `image_pairs` 是否包含 `reference_path` 与 `watermarked_path`, 便于计算基础 PSNR / SSIM 等轻量图像质量指标。

若该预检失败, checklist 会记录 `formal_input_source_preflight_failed`, 这样使用者可以先修复输入结构, 再切换到 Colab GPU 正式运行。

### 直接提供结果文件的结构预检

当正式运行清单使用 `BASELINE_OBSERVATIONS_PATH` 和 `METRIC_ROWS_PATH` 时, helper 会复用仓库内的正式适配器预检文件结构:

- `baseline_observations.json` 必须能被 `experiments.baseline_file_adapter` 读取, 且至少包含 `event_id`、`baseline_id`、`score`、`threshold`。
- `metric_rows.json` 必须能被 `experiments.metric_file_adapter` 读取, 且至少包含一个高级指标字段: `lpips`、`fid` 或 `clip_score`。

该预检只读取轻量结果文件, 不运行 GPU 模型, 也不生成正式 records。其作用是防止空文件、字段缺失文件或仅包含 PSNR / SSIM 的基础指标文件被误认为已经满足正式论文高级指标来源要求。

当预检通过后, cold-start helper 会把直接提供的 `baseline_observations.json` 和 `metric_rows.json` 复制到 `provided_results/`, 并写出 `provided_result_files_manifest.json`。后续 `build_paper_outputs.py` 消费的是该受治理副本, Colab bundle 也会携带副本和 SHA-256 摘要, 因此离线复核者不需要依赖原始 Colab 路径。

`validate_paper_result_evidence.py` 在目标是 Colab bundle 时会继续校验该 manifest: 若正式运行清单声明 baseline 或高级指标来源为 `provided_file`, 但 bundle 中缺少 `provided_result_files_manifest.json`, 或副本文件大小 / SHA-256 与 manifest 不一致, evidence 门禁会失败。该路径不要求 `--require-external-command-results`, 因为它不重新运行或读取外部命令计划结果。


在真正运行 `USE_DRY_RUN_INPUTS = False` 的 Colab 实验前, 建议先生成正式运行清单:

```powershell
python scripts/build_colab_formal_run_checklist.py --workspace-root path\to\workspace --events path\to\events.json --thresholds path\to\thresholds.json --baseline-observations path\to\baseline_observations.json --metric-rows path\to\metric_rows.json --require-pass
```

该清单不会运行模型, 只检查是否已经准备好真实事件来源、阈值、外部 baseline 来源、高级指标来源和实验矩阵覆盖门禁。若启用 `RUN_EXTERNAL_PLANS = True`, 清单还会物化或读取外部命令计划, 并预检第三方 baseline / metric 脚本和工作目录是否存在。Notebook 和 cold-start helper 会通过 repository helper 写出 `colab_formal_run_checklist.json`; 结果构建完成后还会写出 `paper_result_evidence_report.json`, 并把二者纳入 Colab bundle provenance。该清单的 `acceptance_commands` 会同时列出底层 evidence 校验命令和统一的 `run_colab_acceptance_checks.py` 命令, 便于正式运行前明确最终离线验收入口。

### Colab bundle provenance 强校验

`validate_colab_run_bundle.py` 不仅校验 `paper_results_package/` 的 manifest 和文件摘要, 还会要求 bundle 内包含以下正式运行 provenance 文件:

```text
colab_formal_run_checklist.json
paper_result_evidence_report.json
colab_acceptance_report.json
```

其中 `colab_formal_run_checklist.json` 记录运行前输入、阈值、外部 baseline 和高级指标来源是否满足正式实验要求; `paper_result_evidence_report.json` 以最终 `colab_run_bundle/` 为目标, 记录结果包、正式运行清单和外部命令 provenance 是否能够共同作为论文结果证据。bundle 校验会要求该 evidence 报告 `overall_decision = pass` 且 `target_kind = colab_run_bundle`。dry-run 链路中正式运行清单可以是 `overall_decision = fail`, 因为它用于明确声明当前运行不能替代正式 GPU 实验; 但文件本身必须存在并可解析, 这样下载后的 `ceg_colab_run_bundle.zip` 才能被离线复核。

cold-start helper 还会实际运行 `validate_colab_run_bundle.py --require-pass` 和 `validate_paper_result_evidence.py --require-pass`, 并把命令返回码、子报告路径和子报告结论写入 `colab_acceptance_report.json`。该报告现在会用本次 acceptance 命令结果作为覆盖输入, 复核 `colab_formal_result_gap_report.json` 的 post-acceptance readiness, 并在 `report_decisions.formal_result_gap`、`formal_result_gap_decision`、`formal_result_gap_decision_mode` 和 `formal_result_gap_blocking_gap_requirements` 中记录结论、计算模式及剩余阻断项; 但 `overall_decision` 只由 `blocking_report_decisions` 中的 bundle validation 与 paper result evidence 决定, 因此 dry-run 调试链路仍可通过验收并显式保留 `not_ready_for_formal_claims` 提示。dry-run 调试链路会显式传入 `--allow-dry-run` 和 `--allow-missing-experiment-coverage`; 正式运行则不使用这些放宽参数。正式论文声明必须额外确认 `colab_formal_result_gap_report.overall_decision = ready_for_formal_claims`, 不能只依赖 acceptance report 的整体通过结论。

下载后的目录或 zip 也可以独立复跑同一套验收逻辑:

```powershell
python scripts/run_colab_acceptance_checks.py --bundle path\to\colab_run_bundle --allow-dry-run --allow-missing-experiment-coverage --require-pass
python scripts/run_colab_acceptance_checks.py --bundle path\to\ceg_colab_run_bundle.zip --out acceptance_report.json --require-pass
```

## 图像生成产物 Notebook

`paper_workflow/colab_pilot_image_generation_outputs.ipynb` 是专门用于图像生成产物的 Colab 入口。

它的正式运行顺序是:

1. 在 Colab 中运行 Notebook。
2. 从 GitHub 拉取或更新 `CEG` 仓库代码。
3. 如果图像生成需要前序产物, 从 Google Drive 的 `CEG` 工作区加载前序产物结果。
4. 在 Colab GPU 环境中运行仓库脚本和真实外部 backend。
5. 调用真实 SD / watermark backend 生成 clean / watermarked 图像和 image manifests。
6. 调用 `scripts/validate_pilot_image_generation_outputs.py` 验收图像生成输出。
7. 调用 `scripts/build_pilot_stage_progress_summary.py` 刷新阶段摘要。
8. 将图像生成产物打包为 zip, 保存回 Google Drive 的 `CEG/archives/image_generation_outputs/` 目录。

该 Notebook 不直接手写正式 `prompt_plan.json`、`image_pairs.json` 或 image manifests。图像生成产物是否完成只以验收脚本是否通过为准。

## 图像生成真实 backend 更新

当前仓库已补充真实图像生成入口:

```text
scripts/run_pilot_real_image_generation_backend.py
```

该入口在 Colab 中承担以下职责:

1. 读取 `prompt_plan.draft.json`。
2. 通过 diffusers 加载真实 Stable Diffusion 或兼容 text-to-image 模型生成 clean 图像。
3. 调用 CEG 项目内真实 watermark backend 生成 watermarked 图像。默认 backend 为 `ceg_content_chain_embedding`, 不克隆也不调用其他项目。
4. 写出 `prompt_plan.json`、`clean/`、`watermarked/`、`image_pairs.json`、`image_manifests/image_generation_manifest.json` 和 `image_manifests/image_pair_manifest.json`。
5. 自动运行图像生成产物验收报告, 但最终是否完成仍以验收脚本结论为准。

Notebook 只负责拉取 GitHub 仓库、安装运行依赖、从 Google Drive 加载前序产物、执行仓库脚本和归档 zip。`paper_workflow/colab_utils` 不承载真实 SD 采样、水印嵌入或主方法逻辑。


### Colab attestation 与 InSPyReNet 运行准备

图像生成和端到端 Notebook 会在 Colab 会话中定义 `CEG_ATTESTATION_KEY`。该值只写入运行时环境变量, 不写入仓库文件、manifest 或 notebook 输出。如果 Colab secrets 中已经存在同名密钥, Notebook 会优先读取该密钥; 否则会为本次运行生成临时密钥。

InSPyReNet 权重准备属于 Colab 环境准备逻辑, 不属于 `main/` 主方法实现。Notebook 会优先查找:

```text
/content/drive/MyDrive/Models/inspyrenet/ckpt_base.pth
```

如果该文件不存在, Notebook 可从以下地址下载并缓存到 Google Drive:

```text
https://huggingface.co/plemeri/InSPyReNet/resolve/main/ckpt_base.pth
```

随后 Notebook 会把权重复制到 `transparent-background` 常见缓存目录, 并设置 `INSPYRENET_CKPT_PATH`。主方法代码只消费 semantic mask backend 接口, 不包含 Google Drive 权重路径和下载逻辑。


### 外部 baseline Notebook

`paper_workflow/colab_external_baseline_outputs.ipynb` 用于在独立 Colab GPU 会话中运行主表外部 baseline adapter, 并把统一产物保存回 Google Drive。

当前支持的主表方法包括:

```text
Tree-Ring
Gaussian Shading
Shallow Diffuse
T2SMark
```

其中 Tree-Ring、Gaussian Shading 和 Shallow Diffuse 由仓库内 `external_baselines/main_table/*/adapter/run_ceg_eval.py` 直接读取仓库内置 `prompt_plan.json`, 调用 `stabilityai/stable-diffusion-3.5-medium` 生成各自的 clean / watermarked 图像、攻击样本、manifest 和统一 `baseline_observations.json`。T2SMark 的原生 `results.json` 由 `paper_workflow/baselines/colab_t2smark_baseline_outputs.ipynb` 单独生成, 本 Notebook 只把它适配成统一 observation。

Notebook 内部会调用:

```text
scripts/build_sd35_external_adapter_baseline_plan.py
scripts/build_t2smark_adapter_baseline_plan.py
scripts/run_baseline_plan.py
```

输出归档位置为:

```text
/content/drive/MyDrive/CEG/archives/external_baseline_outputs/<RUN_ID>.zip
```

该 zip 的根目录必须包含:

```text
baseline_observations.json
baseline_execution_manifest.json
baseline_command_plan_manifest.json
baseline_command_results.json
```

`colab_paper_results_pipeline.ipynb` 会按同一 `RUN_ID` 从上述 zip 恢复 `baseline_observations.json`, 然后通过 `scripts/import_baseline_observations.py` 导入 paper results package。该 Notebook 不实现 CEG 主方法, 不调用 CEG-WM, 不运行 CEG detection。

## 独立 Colab 会话分阶段流程

正式 `paper_workflow` 现在采用“每个 Notebook 独立冷启动, 通过 Google Drive 阶段归档交接”的约定。机器可读契约位于:

```text
configs/paper_workflow_notebook_contract.json
```

面向人的详细说明位于:

```text
docs/builds/paper_workflow_independent_colab_stage_contract.md
```

推荐正式运行顺序:

1. `colab_pilot_image_generation_outputs.ipynb`
   - 不读取前序 Colab 会话。
   - 从 GitHub 拉取 CEG。
   - 从仓库 `prompts/prompt_plans/{profile}_prompt_plan.json` 读取 prompt。
   - 准备 Hugging Face model snapshot 和 InSPyReNet 权重。
   - 生成 clean / watermarked 图像、`image_pairs.json` 和 image manifests。
   - 将图像生成阶段 zip 写入 `/content/drive/MyDrive/CEG/archives/image_generation_outputs/`。

2. `colab_external_baseline_outputs.ipynb`
   - 可读取图像生成阶段 zip。
   - 运行用户提供的外部 baseline command plan。
   - 将 `baseline_observations.json` 和 `baseline_execution_manifest.json` 打包到 `/content/drive/MyDrive/CEG/archives/external_baseline_outputs/`。

3. `colab_paper_results_pipeline.ipynb`
   - 必须从 Drive 读取图像生成阶段 zip。
   - 可选读取外部 baseline 阶段 zip。
   - 执行 attack、CEG detection、fixed-FPR 校准、质量指标、论文结果包导出和 Drive 归档。

4. `colab_end_to_end_paper_pipeline.ipynb`
   - 单会话 convenience entrypoint。
   - 适合 `paper_main_probe` 或小规模 pilot。
   - 不替代大规模正式分阶段流程。

Google Drive 只作为阶段输入归档、阶段输出归档、模型权重和最终结果包落盘位置; 代码始终从 GitHub 拉取到 Colab 本地 `/content/CEG` 后运行。


## T2SMark 外部 baseline 原生结果 Notebook

`paper_workflow/baselines/colab_t2smark_baseline_outputs.ipynb` 用于在独立 Colab 会话中运行 T2SMark 外部 baseline 本体。该 Notebook 的职责是生成 T2SMark 原生 `results.json`, 不是生成 CEG 统一 baseline observations。

运行顺序如下:

1. 从 GitHub 拉取或更新 `CEG` 仓库到 `/content/CEG`。
2. 从 GitHub 拉取或更新 T2SMark 仓库到 `/content/external_baselines/t2smark/source`。
3. 从 CEG 仓库内置 `prompts/prompt_plans/{profile}_prompt_plan.json` 读取 prompt。
4. 在 Colab 本地 workspace 中生成 T2SMark 可读取的 CSV, 列名为 `Our GT caption`。
5. 调用 T2SMark 的 `run_sd35.py`, 使用 `stabilityai/stable-diffusion-3.5-medium` 生成并检测外部 baseline 水印结果。
6. 将 T2SMark 原生 `results.json` 复制到 Google Drive:

```text
/content/drive/MyDrive/CEG/external_baseline_inputs/t2smark/results.json
```

7. 可选地把 T2SMark 原始输出目录归档到:

```text
/content/drive/MyDrive/CEG/archives/t2smark_baseline_outputs/
```

后续 `paper_workflow/colab_external_baseline_outputs.ipynb` 会读取该 `results.json`, 自动生成 T2SMark adapter plan, 并调用 `scripts/run_baseline_plan.py` 产出 CEG 统一的 `baseline_observations.json` 与 `baseline_execution_manifest.json`。

该 Notebook 不调用 CEG-WM, 不实现 CEG 主方法, 不运行 CEG detection, 不生成论文 records、tables、figures 或 reports。它只承担外部 baseline 原生结果生产职责。
