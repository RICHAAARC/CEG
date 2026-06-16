# Field Registry

## 文档定位

本文档是项目中 governed fields 的登记表。它只记录“当前项目实际使用或模板预留的字段实例”, 不重复解释字段治理规则。

字段 category、后缀要求和清理规则见:

```text
docs/placeholder_random_governance.md
docs/intermediate_state_governance.md
docs/artifact_rebuild.md
```

## 何时需要登记

新增字段只要进入下列任一位置, 就应先登记到本表:

```text
配置文件
records
manifests
tables
reports
Python dict key
测试 fixture
Markdown 示例
Notebook 与 repository module 的跨边界数据
```

函数内部一次性局部变量不需要登记。跨函数、跨文件、跨进程或跨 Notebook 边界保存的中间状态字段需要登记。

## 字段登记表

| field_name | category | required_suffix | allowed_in_records | allowed_in_claims | replacement_required | description |
| --- | --- | --- | --- | --- | --- | --- |
| project_stage | governance | none | true | false | false | 当前项目语义阶段。 |
| target_construction_phase | governance | none | true | false | false | 当前构建目标。 |
| run_id | protocol | none | true | false | false | 一次运行的稳定标识。 |
| record_id | protocol | none | true | false | false | 单条记录的稳定标识。 |
| split | protocol | none | true | false | false | 数据或事件划分。 |
| method_name | protocol | none | true | false | false | 实验记录中的方法名称。 |
| metric_name | protocol | none | true | false | false | 实验记录中的指标名称。 |
| metric_value | protocol | none | true | false | false | 实验记录中的指标数值。 |
| artifact_id | artifact | none | false | false | false | 受治理论文产物的稳定标识。 |
| artifact_type | artifact | none | false | false | false | 受治理论文产物类型, 例如 table、figure、report 或 manifest。 |
| input_paths | artifact | none | false | false | false | 产物重建所需输入路径。 |
| output_paths | artifact | none | false | false | false | 产物重建生成输出路径。 |
| config_digest | artifact | none | false | false | false | 产物重建配置摘要。 |
| code_version | artifact | none | false | false | false | 产物重建所用代码版本。 |
| rebuild_command | artifact | none | false | false | false | 产物重建命令。 |
| claim_id | claim | none | false | true | false | claim 审计表中的声明标识。 |
| evidence_path | claim | none | false | true | false | claim 绑定的证据路径。 |
| backend_placeholder | placeholder | _placeholder | true | false | true | Bootstrap 阶段的占位 backend 字段。 |
| example_digest_random | random | _digest_random | true | false | false | 可复现随机轨迹的 digest 字段。 |
| example_state_intermediate | intermediate | _intermediate | true | false | true | 跨步骤保存的示例中间状态字段, 正式产物生成前需要清理或迁移。 |
| example_artifact_temporary | temporary | _temporary | false | false | true | 可清理的示例临时产物标记。 |
| example_result_cache | cache | _cache | false | false | false | 可由输入、配置和代码重建的示例缓存标记。 |
| event_id | protocol | none | true | false | false | 事件级样本或检测记录标识。 |
| sample_role | protocol | none | true | false | false | 样本在论文协议中的角色, 例如 positive_source 或 clean_negative。 |
| attack_family | protocol | none | true | false | false | 攻击家族名称, 用于鲁棒性分层统计。 |
| attack_condition | protocol | none | true | false | false | 攻击强度或条件描述。 |
| is_watermarked | protocol | none | true | false | false | 事件真实水印标签。 |
| content_score_raw | decision | none | true | false | false | 原始坐标系内容链分数。 |
| content_score_aligned | decision | none | true | false | false | 几何恢复坐标系上的内容链重判分数。 |
| content_margin_raw | decision | none | true | false | false | 原始内容分数相对内容阈值的余量。 |
| content_margin_aligned | decision | none | true | false | false | 恢复后内容分数相对同一内容阈值的余量。 |
| positive_by_content | decision | none | true | false | false | 原始内容链是否直接建立 watermark 主证据。 |
| rescue_eligible | decision | none | true | false | false | 样本是否满足边界失败和几何可信的救回候选条件。 |
| positive_by_geo_rescue | decision | none | true | false | false | 恢复后内容重判是否通过同一内容阈值。 |
| evidence_decision | decision | none | true | false | false | evidence-level watermark 主证据结论。 |
| attestation_pass | decision | none | true | false | false | 事件级 attestation 是否通过。 |
| final_decision | decision | none | true | false | false | final-level 归因结论, 等于 evidence_decision AND attestation_pass。 |
| final_label | decision | none | true | false | false | final-level 离散标签。 |
| geometry_reliable | decision | none | true | false | false | 几何参考系恢复是否满足三项可信度阈值。 |
| registration_confidence | decision | none | true | false | false | 几何配准置信度。 |
| anchor_inlier_ratio | decision | none | true | false | false | 几何锚点内点比例。 |
| recovered_sync_consistency | decision | none | true | false | false | 恢复后同步一致性。 |
| alignment_residual | decision | none | true | false | false | 几何恢复残差。 |
| geometry_recovery_quality_bin | decision | none | true | false | false | 几何恢复质量分桶。 |
| content_fail_reason | decision | none | true | false | false | 内容链失败原因。 |
| geometry_fail_reason | decision | none | true | false | false | 几何链失败原因。 |
| attestation_score | decision | none | true | false | false | 事件 attestation 分数。 |
| payload_probe_score | decision | none | true | false | false | payload probe 诊断分数, 不进入 formal decision。 |
| geo_rescue_blocked_reason | decision | none | true | false | false | geometry rescue 未成立时的阻断原因。 |
| baseline_id | baseline | none | true | false | false | 外部对比 baseline 的稳定标识。 |
| comparison_role | baseline | none | true | false | false | baseline 在论文对比表中的职责。 |
| clean_fpr | metric | none | true | false | false | clean_negative 上的 final-level 误报率。 |
| attacked_negative_fpr | metric | none | true | false | false | attacked_negative 上的 final-level 误报率。 |
| tpr | metric | none | true | false | false | positive_source 上的 final-level 召回率。 |
| final_positive_count | metric | none | true | false | false | final_decision 为真的事件数。 |
| final_negative_count | metric | none | true | false | false | final_decision 为假的事件数。 |
| content_failed_subset_event_count | metric | none | true | false | false | 原始内容链未通过的 positive_source 事件数。 |
| rescue_eligible_event_count | metric | none | true | false | false | formal rescue 候选事件数。 |
| geo_rescue_applied_event_count | metric | none | true | false | false | formal geometry rescue 成立事件数。 |
| positive_by_content_count | metric | none | true | false | false | 原始内容链直接正判事件数。 |
| positive_by_geo_rescue_count | metric | none | true | false | false | 几何救回正判事件数。 |
| rescue_gain | metric | none | true | false | false | final positive 相对 content-only 的净增益。 |
| content_threshold_value | metric | none | true | false | false | 内容链 formal 阈值。 |
| content_threshold_degenerate | metric | none | true | false | false | 内容阈值或正负分布是否退化。 |
| content_threshold_degenerate_reason | metric | none | true | false | false | 内容阈值退化原因。 |
| score_distribution_overlap_indicator | metric | none | true | false | false | positive_source 与 clean_negative 内容分数是否重叠。 |
| score_coverage_rate | metric | none | true | false | false | 某组记录中可用内容分数覆盖率。 |
| artifact_names | artifact | none | false | false | false | 一个重建 bundle 内包含的产物文件名集合。 |
| artifact_digest | artifact | none | false | false | false | 一个重建 bundle 的稳定摘要。 |
| manifest_name | artifact | none | false | false | false | 重建 bundle 的 manifest 文件名。 |
| baseline_display_name | baseline | none | true | false | false | 外部 baseline 的论文显示名称。 |
| baseline_score | baseline | none | true | false | false | 外部 baseline 的检测分数。 |
| baseline_threshold | baseline | none | true | false | false | 外部 baseline 的检测阈值。 |
| baseline_score_name | baseline | none | true | false | false | 外部 baseline 分数字段语义名称。 |
| higher_is_positive | baseline | none | true | false | false | baseline 分数越高是否表示越可能为 positive。 |
| baseline_metadata | baseline | none | true | false | false | baseline 适配器保留的轻量元数据。 |
| profile | protocol | none | true | false | false | 当前运行使用的 active profile。 |
| record_count | metric | none | true | false | false | 当前协议运行生成的记录数量。 |
| ablation_name | protocol | none | true | false | false | CEG 内部机制消融版本名称。 |
| ceg_ablation_variants | protocol | none | true | false | false | 单次协议运行请求输出的 CEG 消融版本集合。 |
| external_baselines | baseline | none | true | false | false | profile 配置声明的外部 baseline 集合。 |
| baseline_observations | baseline | none | true | false | false | 附加到协议事件的外部 baseline observation 列表。 |
| thresholds | protocol | none | true | false | false | CEG 判定所需的阈值集合。 |
| content_threshold | protocol | none | true | false | false | 内容链 formal 阈值。 |
| attestation_threshold | protocol | none | true | false | false | attestation formal 阈值。 |
| rescue_delta_low | protocol | none | true | false | false | 边界失败救回窗口下界宽度。 |
| command | baseline | none | true | false | false | 外部 baseline 的显式命令参数列表。 |
| output_path | artifact | none | true | false | false | 命令或发布包生成的输出路径。 |
| working_directory | baseline | none | true | false | false | 外部 baseline 命令运行目录。 |
| timeout_seconds | baseline | none | true | false | false | 外部 baseline 命令超时时间。 |
| return_code | baseline | none | true | false | false | 外部 baseline 命令返回码。 |
| stdout | baseline | none | true | false | false | 外部 baseline 命令标准输出摘要。 |
| stderr | baseline | none | true | false | false | 外部 baseline 命令标准错误摘要。 |
| observation_count | baseline | none | true | false | false | 外部 baseline observation 行数。 |
| release_package_status | artifact | none | false | false | false | 发布候选包生成状态。 |
| release_package_boundary | artifact | none | false | false | false | 发布候选包边界摘要。 |
| excluded_governance_roots | artifact | none | false | false | false | 发布包排除的治理目录。 |
| bit_correct_count | metric | none | true | true | false | bit-level 解码正确数量, 用于计算 bit accuracy。 |
| bit_total_count | metric | none | true | true | false | bit-level 解码总数量, 用于计算 bit accuracy 和 bit error rate。 |
| bit_accuracy | metric | none | true | true | false | payload bit 恢复准确率。 |
| bit_error_rate | metric | none | true | true | false | payload bit 错误率, 等于 1 - bit_accuracy。 |
| payload_recovered | metric | none | true | true | false | 单事件 payload 是否完整恢复。 |
| payload_recovery_rate | metric | none | true | true | false | 按方法聚合的 payload 完整恢复比例。 |
| psnr | metric | none | true | true | false | 图像水印常用质量指标 PSNR。 |
| ssim | metric | none | true | true | false | 图像水印常用质量指标 SSIM。 |
| lpips | metric | none | true | true | false | 图像感知距离指标 LPIPS。 |
| fid | metric | none | true | true | false | 生成图像分布质量指标 FID。 |
| clip_score | metric | none | true | true | false | 图文语义一致性或条件一致性指标。 |
| detection_auroc | metric | none | true | true | false | 基于检测分数和水印真值计算的 AUROC。 |
| tpr_at_fpr_1_percent | metric | none | true | true | false | clean FPR 不超过 1% 时的 TPR。 |
| tpr_at_fpr_0_1_percent | metric | none | true | true | false | clean FPR 不超过 0.1% 时的 TPR。 |
| metric_mean | metric | none | true | true | false | 长表中某个指标的均值。 |
| metric_coverage_rate | metric | none | true | false | false | 某个指标在 records 中的覆盖率。 |
| figure_id | artifact | none | false | true | false | 可重建论文图表的稳定标识。 |
| chart_type | artifact | none | false | true | false | 图表规格中声明的推荐图表类型。 |
| encodings | artifact | none | false | false | false | 图表规格中的字段到视觉通道映射。 |
| standard_metrics | protocol | none | true | false | false | 事件 payload 中承载标准水印评价指标的映射节点。 |
| baseline_metadata | protocol | none | true | false | false | 外部 baseline observation 中保留的额外审计字段。 |
| image_id | protocol | none | true | true | false | 图像质量指标中用于关联样本或事件的图像标识。 |
| reference_path | artifact | none | true | false | false | 计算图像质量指标时使用的参考图像路径。 |
| watermarked_path | artifact | none | true | false | false | 计算图像质量指标时使用的水印或生成图像路径。 |
| width | metric | none | true | false | false | 图像宽度, 用于质量指标审计。 |
| height | metric | none | true | false | false | 图像高度, 用于质量指标审计。 |
| channel_count | metric | none | true | false | false | 图像通道数, 用于质量指标审计。 |
| mse | metric | none | true | true | false | 图像均方误差。 |
| mae | metric | none | true | true | false | 图像平均绝对误差。 |
| rendered_figures | artifact | none | false | false | false | 图表渲染 manifest 中的 SVG 图表清单。 |
| svg_path | artifact | none | false | true | false | 渲染后 SVG 图表相对路径。 |
| report_path | artifact | none | false | true | false | 渲染后 HTML 报告相对路径。 |
| baseline_command_plan_manifest | artifact | none | false | false | false | 外部 baseline 命令计划 manifest 文件标识。 |
| command | protocol | none | true | false | false | 外部 baseline 执行命令的显式参数列表。 |
| working_directory | protocol | none | true | false | false | 外部 baseline 命令运行目录。 |
| timeout_seconds | protocol | none | true | false | false | 外部 baseline 命令超时时间。 |
| latex_tables | artifact | none | false | true | false | LaTeX 表格产物清单。 |
| latex_table_count | artifact | none | false | true | false | 导出的 LaTeX 表格数量。 |
| metric_rows | protocol | none | true | false | false | 外部高级指标行文件入口。 |
| lpips | metric | none | true | true | false | 外部感知距离指标 LPIPS。 |
| fid | metric | none | true | true | false | 外部图像分布质量指标 FID。 |
| clip_score | metric | none | true | true | false | 外部 CLIP 语义一致性指标。 |
| experiment_matrix_manifest | artifact | none | false | true | false | 论文实验矩阵 manifest 文件标识, 用于审计方法、攻击和 split 覆盖范围。|
| cell_count | metric | none | true | true | false | 实验矩阵或 manifest 中的实验单元数量。|
| cell_id | protocol | none | true | false | false | 单个实验矩阵单元的稳定标识。|
| method_group | protocol | none | true | false | false | 实验矩阵中的方法组, 例如 ceg_ablation 或 external_baseline。|
| attack_level | protocol | none | true | false | false | 攻击强度层级, 例如 none、light、medium 或 strong。|
| expected_artifact_family | artifact | none | true | false | false | 实验单元预期生成的产物家族。|
| command_template | protocol | none | true | false | false | 外部命令模板的显式参数列表。|
| output_path_template | artifact | none | true | false | false | 外部命令模板的输出路径格式。|
| working_directory_template | protocol | none | true | false | false | 外部命令模板的运行目录格式。|
| template_id | protocol | none | true | false | false | 命令模板的稳定标识。|
| template_role | protocol | none | true | false | false | 命令模板对应的执行职责, 例如 external_baseline 或 external_metric。|
| metric_command_plan_manifest | artifact | none | false | false | false | 外部高级指标命令计划 manifest 文件标识。|
| metric_command_count | metric | none | true | false | false | 外部高级指标命令数量。|
| metric_row_count | metric | none | true | true | false | 外部高级指标命令产生的 metric row 数量。|
| external_metric_row_count | metric | none | false | true | false | 正式 evidence 门禁在 Colab bundle 中读取到的外部高级指标行数量。|
| external_metric_fields | metric | none | false | false | false | 正式 evidence 门禁在外部 metric_rows.json 中观察到的指标字段集合。|
| external_advanced_metric_fields | metric | none | false | true | false | 正式 evidence 门禁在外部 metric_rows.json 中观察到的 LPIPS、FID 或 CLIP score 高级指标字段集合。|
| metric_rows_path | artifact | none | false | true | false | 汇总后的外部高级指标行文件相对路径。|
| model_root | protocol | none | true | false | false | 外部 baseline 或指标模型根目录。|
| baseline_root | protocol | none | true | false | false | 外部 baseline 项目根目录。|
| metric_root | protocol | none | true | false | false | 外部高级指标工具根目录。|
| events_path | artifact | none | true | false | false | 外部命令消费的事件 records 输入路径。|
| image_pairs_path | artifact | none | true | false | false | 图像质量或感知指标命令消费的图像配对清单路径。|
| reference_image_root | artifact | none | true | false | false | FID 等分布指标使用的参考图像根目录。|
| generated_image_root | artifact | none | true | false | false | FID 等分布指标使用的生成图像根目录。|
| image_prompt_rows_path | artifact | none | true | false | false | CLIP score 等语义指标使用的图像-文本清单路径。|
| pdf_figures_manifest_path | artifact | none | false | true | false | 一键论文输出摘要中的 PDF 图表 manifest 路径。|
| pdf_figure_count | metric | none | false | true | false | PDF 图表预览中覆盖的 figure 数量。|
| pdf_path | artifact | none | false | true | false | PDF 图表预览文件路径。|
| page_count | metric | none | false | true | false | PDF 图表预览页数。|
| byte_count | metric | none | false | false | false | 导出文件字节数, 用于轻量完整性审计。|
| paper_readiness_report_path | artifact | none | false | true | false | 一键论文输出摘要中的 paper readiness 报告路径。|
| paper_readiness_decision | artifact | none | false | true | false | paper readiness 校验的总体结论, 取值为 pass 或 fail。|
| required_artifacts | artifact | none | false | false | false | paper readiness 配置中要求存在的核心产物文件名集合。|
| required_figure_ids | artifact | none | false | false | false | paper readiness 配置中要求覆盖的论文图表标识集合。|
| required_latex_tables | artifact | none | false | false | false | paper readiness 配置中要求导出的 LaTeX 表格集合。|
| required_methods | protocol | none | true | false | false | paper readiness 配置中要求 records 覆盖的方法、消融和 baseline 集合。|
| required_sample_roles | protocol | none | true | false | false | paper readiness 配置中要求 records 覆盖的样本角色集合。|
| required_table_columns | artifact | none | false | false | false | paper readiness 配置中要求每个表格包含的列集合。|
| minimum_record_count | metric | none | false | false | false | paper readiness 配置中允许通过的最小 record 数量。|
| minimum_figure_count | metric | none | false | false | false | paper readiness 配置中允许通过的最小 figure 数量。|
| minimum_latex_table_count | metric | none | false | false | false | paper readiness 配置中允许通过的最小 LaTeX 表格数量。|
| checks | artifact | none | false | false | false | readiness 或 completion 报告中的逐项检查结果列表。|
| requirement | artifact | none | false | false | false | readiness 或 completion 报告中单个检查项的名称。|
| status | artifact | none | false | false | false | readiness 或 completion 报告中单个检查项的状态。|
| paper_dry_run_inputs_manifest | artifact | none | false | false | false | 端到端论文 readiness dry-run 输入 manifest 文件标识。|
| fixture_role | artifact | none | false | false | false | fixture 在产物链路中的用途, 例如 paper_readiness_dry_run。|
| fixture_digest | artifact | none | false | false | false | dry-run 输入 bundle 的稳定摘要。|
| baseline_observations_path | artifact | none | false | false | false | dry-run 或正式输出链路中 baseline observation 输入文件路径。|
| thresholds_path | artifact | none | false | false | false | dry-run 或正式输出链路中阈值输入文件路径。|
| baseline_observation_count | metric | none | false | false | false | dry-run 输入或 baseline runner 输出中的 baseline observation 数量。|
| paper_readiness_dry_run_summary | artifact | none | false | true | false | 端到端 paper readiness dry-run 运行摘要文件标识。|
| paper_outputs_root | artifact | none | false | true | false | dry-run 摘要中完整论文输出包相对目录。|
| rate_confidence_intervals | artifact | none | false | true | false | 论文率指标 Wilson 置信区间表文件标识。|
| method_pairwise_delta_table | artifact | none | false | true | false | 方法相对参考方法的率指标差值表文件标识。|
| method_group_comparison_table | artifact | none | false | true | false | 方法组对比表文件标识, 用于同时区分 CEG 主方法、内部消融和外部 baseline。|
| success_count | metric | none | true | true | false | 率指标分子, 例如正例检出数或负例误报数。|
| total_count | metric | none | true | true | false | 率指标分母, 例如对应样本角色的事件数量。|
| rate_value | metric | none | true | true | false | 由 success_count / total_count 得到的率指标点估计。|
| ci_lower | metric | none | true | true | false | 置信区间下界。|
| ci_upper | metric | none | true | true | false | 置信区间上界。|
| ci_method | metric | none | true | false | false | 置信区间或差值区间使用的方法说明。|
| reference_method | protocol | none | true | true | false | 方法差值表中的参考方法名称。|
| method_rate_value | metric | none | true | true | false | 方法自身的率指标点估计。|
| reference_rate_value | metric | none | true | true | false | 参考方法的率指标点估计。|
| rate_delta | metric | none | true | true | false | 方法率指标相对参考方法的差值。|
| delta_ci_lower | metric | none | true | true | false | 差值区间下界。|
| delta_ci_upper | metric | none | true | true | false | 差值区间上界。|
| detection_roc_curve | artifact | none | false | true | false | 检测 ROC 曲线 CSV 产物标识。|
| score_histogram_table | artifact | none | false | true | false | 检测分数分布直方表 CSV 产物标识。|
| operating_point_table | artifact | none | false | true | false | 默认 operating threshold 下的混淆计数和率指标表。|
| point_index | metric | none | true | false | false | ROC 曲线点在单个方法内的排序索引。|
| threshold_label | metric | none | true | false | false | ROC 曲线阈值点类型, 例如 above_max、score_threshold 或 below_min。|
| threshold_value | metric | none | true | true | false | ROC 曲线或阈值扫描中的检测分数阈值。|
| true_positive_count | metric | none | true | true | false | operating point 或 ROC 点中的真阳性数量。|
| false_positive_count | metric | none | true | true | false | operating point 或 ROC 点中的假阳性数量。|
| true_negative_count | metric | none | true | true | false | operating point 中的真阴性数量。|
| false_negative_count | metric | none | true | true | false | operating point 中的假阴性数量。|
| positive_count | metric | none | true | true | false | 检测曲线或 operating point 中的正样本数量。|
| negative_count | metric | none | true | true | false | 检测曲线或 operating point 中的负样本数量。|
| label_name | protocol | none | true | false | false | score 分布表中的标签分组名称。|
| bin_index | metric | none | true | false | false | score 分布直方表中的分箱索引。|
| score_bin_lower | metric | none | true | true | false | score 分布分箱下界。|
| score_bin_upper | metric | none | true | true | false | score 分布分箱上界。|
| score_bin_count | metric | none | true | true | false | score 分布分箱内样本数量。|
| score_bin_rate | metric | none | true | true | false | score 分布分箱内样本占同方法同标签样本的比例。|
| operating_threshold | metric | none | true | true | false | operating point 使用的默认检测阈值。|
| paper_results_report | artifact | none | false | true | false | 一键论文输出生成的 Markdown 结果报告文件标识。|
| paper_results_report_manifest | artifact | none | false | true | false | Markdown 结果报告 manifest 文件标识。|
| paper_results_report_path | artifact | none | false | true | false | paper_outputs_summary 中的 Markdown 结果报告路径。|
| paper_results_report_manifest_path | artifact | none | false | true | false | paper_outputs_summary 中的 Markdown 结果报告 manifest 路径。|
| source_paths | artifact | none | false | false | false | 报告 manifest 中记录的来源产物路径集合。|
| readiness_decision | artifact | none | false | true | false | 报告 manifest 中记录的 readiness 总体结论。|
| paper_claim_audit | artifact | none | false | true | false | supported claims 到受治理产物的审计报告文件标识。|
| claim_text | claim | none | false | true | false | claim audit 中面向论文读者的声明文本。|
| supporting_artifacts | claim | none | false | true | false | 支撑某个 claim 的 artifact 文件名集合。|
| supporting_methods | claim | none | false | true | false | 支撑某个 claim 必须覆盖的方法、内部消融或外部 baseline 集合。|
| supporting_figures | claim | none | false | true | false | 支撑某个 claim 必须覆盖的 figure_id 集合。|
| missing_artifacts | claim | none | false | false | false | claim audit 中缺失的 artifact 文件名集合。|
| empty_artifacts | claim | none | false | false | false | claim audit 中存在但 payload 为空的 artifact 文件名集合。|
| missing_methods | claim | none | false | false | false | claim audit 中缺失的方法、消融或 baseline 集合。|
| missing_figures | claim | none | false | false | false | claim audit 中缺失的 figure_id 集合。|
| claim_count | metric | none | false | true | false | claim audit 覆盖的论文声明数量。|
| supported_claim_count | metric | none | false | true | false | claim audit 中已经通过受治理产物支撑的声明数量。|
| failed_claim_count | metric | none | false | false | false | claim audit 中未通过支撑检查的声明数量。|
| paper_results_package_manifest | artifact | none | false | true | false | 论文结果输出包 manifest 文件标识。|
| paper_results_package_validation | artifact | none | false | true | false | 论文结果输出包 manifest 校验报告文件标识。|
| package_status | artifact | none | false | true | false | 结果包导出状态, 例如 complete 或 incomplete。|
| source_output_root | artifact | none | false | false | false | 结果包导出所依据的 build_paper_outputs 输出目录。|
| copied_files | artifact | none | false | true | false | 结果包中复制的相对文件路径集合。|
| missing_files | artifact | none | false | false | false | 结果包导出或校验中缺失的文件路径集合。|
| file_count | metric | none | false | true | false | 结果包 manifest 中登记的文件数量。|
| package_digest | artifact | none | false | true | false | 结果包文件清单和文件摘要的稳定 digest。|
| files | artifact | none | false | false | false | 结果包 manifest 中逐文件摘要条目集合。|
| relative_path | artifact | none | false | false | false | 结果包内文件的相对路径。|
| sha256 | artifact | none | false | false | false | 结果包内单个文件的 SHA-256 摘要。|
| source_manifests | artifact | none | false | false | false | 结果包 manifest 所引用的来源 manifest 路径集合。|
| claim_audit_decision | artifact | none | false | true | false | 结果包 manifest 中记录的 claim audit 总体结论。|
| colab_environment_summary | artifact | none | false | false | false | Colab Notebook 运行环境摘要文件标识。|
| colab_command_plan | artifact | none | false | false | false | Colab 冷启动链路中准备输入、构建结果和导出结果包的命令计划。|
| colab_cold_start_summary | artifact | none | false | true | false | Colab 冷启动端到端运行摘要文件标识。|
| is_colab_runtime | protocol | none | false | false | false | 当前运行环境是否为 Google Colab。|
| use_dry_run_inputs | protocol | none | false | false | false | Colab 链路是否使用仓库生成的 dry-run 输入。|
| prepare_command | protocol | none | false | false | false | Colab 链路中生成或准备输入的命令。|
| build_command | protocol | none | false | false | false | Colab 链路中调用 build_paper_outputs.py 的命令。|
| package_command | protocol | none | false | false | false | Colab 链路中导出 paper results package 的命令。|
| command_results | artifact | none | false | false | false | Colab 链路中各子命令的结构化执行结果。|
| run_external_plans | protocol | none | false | false | false | Colab 链路是否运行外部 baseline 与高级指标命令计划。|
| external_plan_steps | protocol | none | false | false | false | Colab 命令计划中外部 baseline 与 metric 的物化和执行步骤集合。|
| materialize_baseline_command | protocol | none | false | false | false | Colab 中由模板生成 baseline command plan 的命令。|
| baseline_execution_command | protocol | none | false | false | false | Colab 中执行 baseline command plan 的命令。|
| materialize_metric_command | protocol | none | false | false | false | Colab 中由模板生成 metric command plan 的命令。|
| metric_execution_command | protocol | none | false | false | false | Colab 中执行 metric command plan 的命令。|
| nvidia_smi | artifact | none | false | false | false | Colab 环境摘要中的 nvidia-smi 探测结果。|
| torch_cuda | artifact | none | false | false | false | Colab 环境摘要中的 torch.cuda 探测结果。|
| colab_input_manifest | artifact | none | false | false | false | Colab 运行前输入路径与预期输出契约清单。|
| missing_required_inputs | artifact | none | false | false | false | Colab 输入清单中缺失的必要输入路径集合。|
| expected_outputs | artifact | none | false | false | false | Colab 链路完成后预期存在的关键输出路径集合。|
| paper_experiment_coverage_report | artifact | none | false | true | false | 论文实验矩阵覆盖率报告文件标识, 用于说明当前 records 是否覆盖所选 profile 的实验矩阵。|
| expected_key_count | metric | none | false | true | false | 实验覆盖率报告中按 split、method、sample_role 和 attack_condition 去重后的预期组合数量。|
| observed_key_count | metric | none | false | true | false | 实验覆盖率报告中从 records 观察到的去重组合数量。|
| covered_key_count | metric | none | false | true | false | 实验覆盖率报告中预期组合与实际组合相交的数量。|
| missing_key_count | metric | none | false | false | false | 实验覆盖率报告中预期存在但 records 缺失的组合数量。|
| unexpected_key_count | metric | none | false | false | false | 实验覆盖率报告中 records 存在但矩阵未声明的组合数量。|
| coverage_rate | metric | none | false | true | false | 实验覆盖率报告中的覆盖比例。|
| axis_coverage | artifact | none | false | false | false | 实验覆盖率报告中按单个实验轴展开的覆盖摘要。|
| method_group_coverage | artifact | none | false | true | false | 实验覆盖率报告中按 ceg_main、ceg_ablation 和 external_baseline 聚合的覆盖摘要。|
| missing_examples | artifact | none | false | false | false | 实验覆盖率报告中缺失矩阵组合的有限示例。|
| unexpected_examples | artifact | none | false | false | false | 实验覆盖率报告中未被矩阵声明但出现在 records 中的有限示例。|
| coverage_digest | artifact | none | false | true | false | 实验覆盖率报告中预期键和观察键的稳定摘要。|
| colab_formal_result_gap_report | artifact | none | false | true | false | Colab 正式论文结果缺口报告, 用于说明当前运行距离正式结果声明仍缺哪些证据。 |
| blocking_gap_count | metric | none | false | true | false | 正式论文结果缺口报告中阻断性缺口数量。 |
| blocking_gap_requirements | artifact | none | false | true | false | 正式论文结果缺口报告中阻断性缺口对应的 requirement 集合。 |
| formal_result_gap_report_path | artifact | none | false | false | false | archive manifest 中记录的正式论文结果缺口报告路径。 |
| non_dry_run_inputs_used | protocol | none | false | false | false | 正式论文结果缺口报告中检查当前运行是否使用非 dry-run 输入。 |
| strict_paper_result_evidence_passed | artifact | none | false | true | false | 正式论文结果缺口报告中检查 evidence 是否在严格参数下通过。 |
| strict_colab_acceptance_passed | artifact | none | false | true | false | 正式论文结果缺口报告中检查 Colab acceptance 是否在严格参数下通过。 |
| colab_formal_input_contract | artifact | none | false | false | false | Colab 正式实验输入契约 manifest, 用于声明 events、thresholds、sample manifest、baseline observations、metric rows 和第三方脚本接口。|
| contract_version | artifact | none | false | false | false | Colab 正式输入契约的稳定版本标识。|
| contract_digest | artifact | none | false | true | false | Colab 正式输入契约中输入文件、第三方接口和验收要求的稳定摘要。|
| input_files | artifact | none | false | false | false | Colab 正式输入契约中按 role 列出的输入文件要求集合。|
| third_party_command_interfaces | artifact | none | false | false | false | Colab 正式输入契约中声明的外部 baseline 和高级指标脚本接口集合。|
| formal_acceptance_requirements | artifact | none | false | true | false | Colab 正式输入契约中列出的正式论文结果验收条件。|
| colab_formal_runbook | artifact | none | false | false | false | Colab 正式运行说明书, 用于串联输入准备、模板、正式清单、缺口报告和验收命令。|
| formal_runbook_path | artifact | none | false | false | false | archive manifest 或 summary 中记录的 Colab 正式运行说明书路径。|
| formal_input_templates_manifest | artifact | none | false | false | false | Colab 正式输入模板 manifest, 用于记录可填写输入模板的位置、用途、字段和摘要。|
| formal_input_templates | artifact | none | false | false | false | Colab workspace 中保存 events、thresholds、sample manifest、baseline observations、metric rows 和 image pairs 模板的目录。|
| template_count | metric | none | false | false | false | 正式输入模板 manifest 中声明的模板文件数量。|
| template_roles | artifact | none | false | false | false | 正式输入模板 manifest 中按输入角色列出的模板集合。|
| template_manifest_digest | artifact | none | false | true | false | 正式输入模板 manifest 中模板条目的稳定摘要。|
| colab_paper_result_index | artifact | none | false | true | false | Colab 论文结果索引 manifest, 显式映射论文表格、图表、指标、baseline、消融和交付件路径。 |
| colab_paper_result_semantic_check_summary | artifact | none | false | true | false | Colab cold start summary 中提升展示的论文结果内容结构校验汇总。 |
| colab_paper_result_semantic_check_failures | artifact | none | false | true | false | Colab cold start summary 中提升展示的论文结果内容结构校验失败 result_id 集合。 |
| colab_paper_result_required_group_failures | artifact | none | false | true | false | Colab cold start summary 中提升展示的必需论文结果组缺失集合。 |
| colab_paper_result_production_trace_summary | artifact | none | false | true | false | Colab cold start summary 中提升展示的论文结果生产追踪覆盖率汇总。 |
| indexed_results | artifact | none | false | false | false | Colab 论文结果索引中逐项列出的结果文件条目集合。 |
| result_group | artifact | none | false | false | false | 论文结果索引中的结果组, 例如 watermark_standard_metrics、baseline_and_ablation 或 figures。 |
| result_id | artifact | none | false | false | false | 论文结果索引中单个结果文件的稳定标识。 |
| required_for_paper_outputs | protocol | none | false | false | false | 论文结果索引中标记某文件是否为论文结果产物链路必需文件。 |
| required_missing | artifact | none | false | true | false | 论文结果索引中缺失的必需结果文件相对路径集合。 |
| required_result_group_summary | artifact | none | false | true | false | 论文结果索引中按必需结果组聚合的完整性判定, 用于区分标准指标、baseline / 消融、图表和报告等论文结果类型是否齐备。 |
| required_result_group_count | artifact | none | false | false | false | 论文结果索引中包含必需论文结果的结果组数量。 |
| required_result_group_pass_count | artifact | none | false | false | false | 论文结果索引中已经通过完整性判定的必需结果组数量。 |
| required_result_group_failures | artifact | none | false | true | false | 论文结果索引中仍缺少必需结果文件的结果组集合。 |
| missing_required_results | artifact | none | false | false | false | 单个论文结果组内缺失的必需 result_id 集合。 |
| semantic_check | artifact | none | false | false | false | 论文结果索引中针对单个关键结果文件的轻量内容结构校验结果。 |
| semantic_check_summary | artifact | none | false | true | false | 论文结果索引中关键结果文件内容结构校验的汇总计数和必需失败集合。 |
| semantic_check_failures | artifact | none | false | true | false | 论文结果索引中已经存在但未通过内容结构校验的必需结果 result_id 集合。 |
| production_trace | artifact | none | false | false | false | 论文结果索引中单个结果文件的生产追踪, 说明该文件由哪些仓库步骤生成、依赖哪些输入并由哪些门禁验收。 |
| production_trace_summary | artifact | none | false | true | false | 论文结果索引中生产追踪覆盖率汇总, 用于发现仍缺少生产步骤或验收门禁的 result_id。 |
| producer_steps | artifact | none | false | false | false | production_trace 中列出的结果生成脚本、模块函数或 Colab helper 步骤。 |
| required_inputs | artifact | none | false | false | false | production_trace 中列出的生成该结果所需上游输入、模板或外部证据来源。 |
| validation_gates | artifact | none | false | false | false | production_trace 中列出的结果进入论文链路前必须通过的校验、证据或验收门禁。 |
| traceable_total | artifact | none | false | false | false | production_trace_summary 中已具备生产步骤和验收门禁追踪的结果条目数量。 |
| missing_trace_count | artifact | none | false | true | false | production_trace_summary 中缺少生产步骤或验收门禁追踪的结果条目数量。 |
| missing_trace_result_ids | artifact | none | false | true | false | production_trace_summary 中缺少生产追踪的 result_id 集合。 |
| colab_paper_result_index_semantic_checks_passed | artifact | none | false | true | false | Colab bundle 验收中检查论文结果索引整体通过、必需结果组无失败且语义校验失败数为 0 的门禁项。 |
| colab_paper_result_index_production_trace_complete | artifact | none | false | true | false | Colab bundle 验收中检查论文结果索引所有 result_id 都具备生产步骤与验收门禁追踪的门禁项。 |
| paper_result_index_production_trace_complete | artifact | none | false | true | false | Colab 正式结果缺口报告中检查论文结果索引生产追踪是否完整的阻断项。 |
| result_index_digest | artifact | none | false | true | false | 论文结果索引条目的稳定摘要。 |
| colab_output_layout_manifest | artifact | none | false | true | false | Colab 结果类型目录 manifest, 用于审计每类输出在 Drive 根目录下的落盘位置。 |
| drive_output_root | artifact | none | false | false | false | Colab 结果落盘根目录, Notebook 默认指向 /content/drive/MyDrive/CEG。 |
| output_layout | artifact | none | false | false | false | Colab 结果根目录下按结果类型划分的子目录映射。 |
| result_type_directories | artifact | none | false | false | false | 输出布局 manifest 中按结果类型列出的目录、用途、存在状态和文件数量。 |
| layout_digest | artifact | none | false | true | false | 输出布局 manifest 对结果类型目录条目的稳定摘要。 |
| archives_root | artifact | none | false | false | false | Colab workspace 中保存可下载 zip 和 sidecar manifest 的 archives 目录。 |
| matrix_root | artifact | none | false | false | false | Colab workspace 中保存 experiment_matrix.json 和 manifest 的目录。|
| experiment_matrix_path | artifact | none | false | false | false | Colab 命令计划传给 build_paper_outputs.py 的 experiment_matrix.json 路径。|
| matrix_command | protocol | none | false | false | false | Colab 冷启动链路中生成实验矩阵的命令。|
| require_experiment_coverage | protocol | none | false | false | false | Colab 或 build_paper_outputs.py 是否要求实验矩阵覆盖率通过。|
| preflight_outputs | artifact | none | false | false | false | Colab 正式构建前预期生成的实验矩阵等预检产物路径集合。|
| sample_manifest_path | artifact | none | false | false | false | Colab 或样本转换脚本消费的真实实验样本清单路径。|
| sample_event_build_manifest | artifact | none | false | false | false | 样本清单转换为协议 events.json 后写出的构建 manifest 文件标识。|
| sample_row_count | metric | none | false | false | false | 样本清单中的原始样本行数量。|
| image_pair_count | metric | none | false | false | false | 从样本清单中提取出的 reference_path 与 watermarked_path 图像配对数量。|
| sample_event_digest | artifact | none | false | false | false | 样本清单转换得到的 events、image_pairs 和 thresholds 的稳定摘要。|
| compute_basic_image_metrics | protocol | none | false | false | false | Colab 链路是否调用轻量图像质量指标脚本计算 PSNR 和 SSIM。|
| basic_metric_command | protocol | none | false | false | false | Colab 链路中调用 compute_image_quality_metrics.py 的命令。|
| basic_metric_root | artifact | none | false | false | false | Colab workspace 中保存轻量图像质量指标行的目录。|
| basic_metric_rows_path | artifact | none | false | false | false | 轻量图像质量指标输出 metric_rows.json 路径。|
| generated_image_pairs_path | artifact | none | false | false | false | 由样本清单转换脚本生成的 image_pairs.json 路径。|
| source_input_paths | artifact | none | false | false | false | Colab input manifest 中记录的用户提供源输入路径集合。|
| threshold_calibration_report | artifact | none | false | false | false | 从 calibration 样本清单校准内容阈值后写出的审计报告文件标识。|
| threshold_calibration_digest | artifact | none | false | false | false | 阈值校准配置、分数摘要和阈值映射的稳定摘要。|
| calibrate_thresholds | protocol | none | false | false | false | Colab 链路是否在缺少 thresholds.json 时从样本清单自动校准阈值。|
| threshold_target_fpr | metric | none | false | false | false | 阈值校准使用的 clean negative 目标 FPR。|
| threshold_calibration_split | protocol | none | false | false | false | 阈值校准使用的 split 名称。|
| threshold_root | artifact | none | false | false | false | Colab workspace 中保存阈值校准输出的目录。|
| calibrated_thresholds_path | artifact | none | false | false | false | Colab 链路自动校准得到的 thresholds.json 路径。|
| threshold_calibration_command | protocol | none | false | false | false | Colab 链路中调用 calibrate_thresholds_from_sample_manifest.py 的命令。|
| negative_score_count | metric | none | false | false | false | 阈值校准中用于估计 FPR 的 negative 分数数量。|
| observed_false_positive_count | metric | none | false | false | false | 校准阈值在 calibration negative 上产生的误报数量。|
| observed_fpr | metric | none | false | false | false | 校准阈值在 calibration negative 上观察到的 FPR。|
| colab_run_bundle_manifest | artifact | none | false | true | false | Colab 运行级 bundle 的 manifest 文件标识。|
| colab_run_bundle_root | artifact | none | false | true | false | Colab workspace 中保存运行级 bundle 的目录。|
| colab_run_bundle_manifest_path | artifact | none | false | true | false | Colab summary 中记录的运行级 bundle manifest 路径。|
| colab_run_bundle_file_count | metric | none | false | true | false | Colab 运行级 bundle 中复制的文件数量。|
| bundle_root | artifact | none | false | false | false | 导出的运行级 bundle 根目录。|
| bundle_digest | artifact | none | false | true | false | Colab 运行级 bundle 文件条目的稳定摘要。|
| colab_bundle_archive_manifest | artifact | none | false | true | false | Colab 下载 zip 的 sidecar manifest, 记录 archive 路径、大小、SHA-256 和离线验收命令。|
| colab_bundle_archive_manifest_path | artifact | none | false | true | false | Colab cold start summary 中记录的 archive manifest 路径。|
| colab_bundle_archive_path | artifact | none | false | true | false | Colab cold start summary 中记录的可下载 zip 路径。|
| colab_bundle_archive_sha256 | artifact | none | false | true | false | Colab 可下载 zip 的 SHA-256 摘要。|
| colab_bundle_offline_acceptance_command | protocol | none | false | true | false | 下载 zip 后可在本地或 CI 复跑的统一验收命令。|
| colab_acceptance_command | protocol | none | false | false | false | archive manifest 中记录的 Colab 会话内绝对路径验收命令。|
| archive_manifest_path | artifact | none | false | false | false | archive manifest 中记录的 sidecar manifest 自身路径。 |
| output_layout_manifest_path | artifact | none | false | false | false | archive manifest 中记录的 Colab 输出布局 manifest 路径。 |
| paper_result_index_path | artifact | none | false | false | false | archive manifest 中记录的 Colab 论文结果索引路径。 |
| archive_size_bytes | metric | none | false | false | false | Colab 可下载 zip 的字节大小。|
| offline_acceptance_command | protocol | none | false | false | false | archive manifest 中记录的下载后验收命令。|
| missing_optional | artifact | none | false | false | false | Colab 运行级 bundle 中因未启用相应流程而缺失的可选 provenance 文件。|
| colab_run_bundle_validation | artifact | none | false | true | false | Colab 运行级 bundle 的自校验报告文件标识。|
| validation_decision | artifact | none | false | true | false | Colab 运行级 bundle manifest 返回给 summary 的校验结论。|
| colab_run_bundle_validation_decision | artifact | none | false | true | false | Colab cold start summary 中记录的运行级 bundle 校验结论。|
| validated_bundle_path | artifact | none | false | false | false | 独立 Colab bundle 校验 CLI 实际定位并校验的 bundle 根目录路径。|
| validated_archive_path | artifact | none | false | false | false | 独立 Colab bundle 校验 CLI 处理 zip 输入时记录的压缩包路径。|
| paper_result_evidence_report | artifact | none | false | true | false | 正式论文结果证据完整性报告文件标识, 用于区分 dry-run 链路通过和正式实验结果通过。|
| evidence_target_path | artifact | none | false | false | false | 正式证据校验 CLI 接收的 paper outputs、paper results package 或 Colab bundle 目标路径。|
| target_kind | artifact | none | false | false | false | 正式证据校验识别到的目标类型, 例如 paper_output_directory、paper_results_package 或 colab_run_bundle。|
| allow_dry_run | protocol | none | false | false | false | 正式证据校验是否允许 dry-run 标记存在, 该字段为 true 时只能说明链路调试通过。|
| require_external_command_results | protocol | none | false | false | false | 正式证据校验是否要求 Colab bundle 中 `external_plan` 来源的外部 baseline 和高级指标命令结果均通过; `provided_file` 来源改由 `provided_result_files_manifest` 校验。|
| minimum_quality_metric_coverage | metric | none | false | true | false | 正式证据校验要求每个必需方法在 PSNR、SSIM、LPIPS、FID 和 CLIP score 上达到的最低覆盖率。|
| gpu_readiness | artifact | none | false | true | false | Colab formal checklist 中记录的 GPU 运行时预检结果。|
| require_gpu_for_external_plans | protocol | none | false | true | false | 正式外部 baseline / metric 计划是否要求 GPU runtime。|
| required_for_external_plans | protocol | none | false | false | false | GPU readiness 子结构中记录的外部计划 GPU 要求。|
| gpu_available | artifact | none | false | false | false | GPU readiness 子结构中记录的当前运行时是否检测到 GPU。|
| checked_for_formal_external_plans | protocol | none | false | false | false | GPU readiness 子结构中记录本次清单是否针对正式外部计划执行 GPU 门禁。|
| colab_formal_run_checklist | artifact | none | false | true | false | Colab 正式实验运行清单文件标识, 用于在执行 GPU 任务前审计输入、外部结果来源和验收命令。|
| baseline_source_mode | protocol | none | false | false | false | Colab 正式运行清单中的 baseline 来源模式, 例如 provided_file、external_plan 或 missing。|
| metric_source_mode | protocol | none | false | false | false | Colab 正式运行清单中的高级指标来源模式, 例如 provided_file、external_plan 或 missing。|
| formal_input_source_preflight | artifact | none | false | false | false | Colab 正式运行清单中对 events、thresholds、sample manifest 和 image pairs 输入源进行结构预检的结果。|
| formal_input_source_violation_count | metric | none | false | true | false | Colab 正式运行清单中正式输入源结构预检发现的问题数量。|
| provided_result_file_preflight | artifact | none | false | false | false | Colab 正式运行清单中对用户直接提供的 baseline observation 与高级指标文件进行结构预检的结果。|
| provided_result_file_violation_count | metric | none | false | true | false | Colab 正式运行清单中直接提供结果文件结构预检发现的问题数量。|
| provided_result_files_manifest | artifact | none | false | true | false | Colab workspace 中直接提供结果文件副本的 manifest, 记录源路径、bundle 内目标路径和摘要。|
| provided_results_root | artifact | none | false | false | false | Colab workspace 中保存直接提供 baseline / metric 文件副本的目录。|
| copied_files | artifact | none | false | false | false | provided_result_files_manifest 中已经复制并可复核摘要的文件条目集合。|
| missing_sources | artifact | none | false | false | false | provided_result_files_manifest 中复制前缺失的用户源文件集合。|
| issues | artifact | none | false | false | false | Colab 正式运行清单中的预检问题集合。|
| blocking_issue_count | metric | none | false | true | false | Colab 正式运行清单中阻断正式运行的预检问题数量。|
| acceptance_commands | protocol | none | false | true | false | Colab 正式运行清单中建议在运行完成后执行的验收命令集合。|
| colab_acceptance_report | artifact | none | false | true | false | Colab 冷启动完成后实际运行验收 CLI 的结构化报告。|
| colab_acceptance_decision | artifact | none | false | true | false | Colab cold start summary 中记录的最终验收报告结论。|
| colab_acceptance_report_decisions | artifact | none | false | true | false | Colab acceptance report 中各个验收子报告的通过状态集合。|
| blocking_report_decisions | artifact | none | false | true | false | Colab acceptance report 中决定 overall_decision 的阻断性子报告结论集合, 当前包含 bundle validation 和 paper result evidence。|
| colab_acceptance_blocking_report_decisions | artifact | none | false | true | false | Colab cold start summary 中提升展示的阻断性 acceptance 子报告结论集合。|
| formal_result_gap_decision | artifact | none | false | true | false | Colab acceptance report 中记录的 formal_result_gap 子报告结论, 用于提示当前运行是否已具备正式论文声明 readiness。|
| colab_acceptance_formal_result_gap_decision | artifact | none | false | true | false | Colab cold start summary 中提升展示的 formal_result_gap_decision。|
| formal_result_gap | artifact | none | false | true | false | Colab acceptance report 的 report_decisions 中记录正式论文结果缺口报告 overall_decision 的子报告键。|
| source_bundle_path | artifact | none | false | false | false | 独立 Colab acceptance CLI 接收的 bundle 目录或 zip 路径。|
| validated_archive_path | artifact | none | false | false | false | 独立 Colab acceptance CLI 复核 zip 文件时记录的原始压缩包路径。|
| colab_formal_run_checklist_path | artifact | none | false | true | false | Colab cold start summary 中记录的正式实验运行清单路径。|
| colab_formal_run_checklist_decision | artifact | none | false | true | false | Colab cold start summary 中记录的正式实验运行清单结论。|
| paper_result_evidence_report_path | artifact | none | false | true | false | Colab cold start summary 中记录的正式结果证据完整性报告路径。|
| paper_result_evidence_decision | artifact | none | false | true | false | Colab cold start summary 中记录的正式结果证据完整性报告结论。|
| external_plan_preflight | artifact | none | false | false | false | Colab 正式运行清单中对外部 baseline 和高级指标命令计划的脚本及工作目录预检结果。|
| external_command_plan_violation_count | metric | none | false | true | false | Colab 正式运行清单中外部命令计划预检发现的脚本或工作目录问题数量。|
| plan_kind | protocol | none | false | false | false | 外部命令计划预检中的计划类型, 例如 baseline 或 metric。|
| template_id | protocol | none | true | false | false | 外部命令模板或预检条目的稳定标识。|
