# external baseline 项目修复记录 - 2026-06-19

## 修复目标

本次修复面向 `paper_workflow/colab_external_baseline_outputs.ipynb` 与 T2SMark adapter 的结果完整性问题。目标是使 external baseline 阶段产物更适合被后续 `paper_results` 流程消费。

## 已修复问题

### 1. T2SMark observation 缺少 final_decision

修复文件:

```text
external_baselines/main_table/t2smark/adapter/run_ceg_eval.py
```

修复内容:

- 在 `_observation(...)` 中显式写入 `final_decision`。
- 判定规则为 `score >= threshold`。
- 同时把 `score` 和 `threshold` 规范化为 `float`, 避免后续 CSV / JSON 汇总时出现字符串比较或类型不一致。

该修复属于统一 observation 契约补齐, 不改变 T2SMark 方法分数本身。

### 2. image_pairs 路径重写报告未进入 external baseline 归档

修复文件:

```text
paper_workflow/colab_external_baseline_outputs.ipynb
```

修复内容:

- external baseline notebook 解压图像生成阶段 zip 后, 会调用 `rewrite_image_pairs_for_restored_archive(...)`。
- 现在会把 `image_pairs_restored_path_rewrite_report.json` 从 `inputs/images/` 复制到 `external_baselines/` 根目录。
- 因为 external baseline 阶段最终归档的是 `external_baselines/` 目录, 所以该报告现在会随 zip 一起落盘。

该修复属于 Colab 跨会话路径恢复 provenance 补齐, 不改变任何水印算法。

## 已执行校验

已完成以下轻量校验:

```text
syntax ok external_baselines/main_table/t2smark/adapter/run_ceg_eval.py
notebook code syntax ok paper_workflow/colab_external_baseline_outputs.ipynb
t2smark final_decision smoke ok
```

烟测确认 T2SMark 输出行包含 `final_decision`, 且 clean negative 为 False, positive source 为 True。

## 需要重跑

需要重跑:

```text
paper_workflow/colab_external_baseline_outputs.ipynb
```

不需要重跑:

```text
paper_workflow/colab_pilot_image_generation_outputs.ipynb
paper_workflow/baselines/colab_t2smark_baseline_outputs.ipynb
```

前提是 Drive 中仍存在:

```text
/content/drive/MyDrive/CEG/archives/image_generation_outputs/paper_main_probe_image_generation_outputs.zip
/content/drive/MyDrive/CEG/external_baseline_inputs/t2smark/results.json
```
