<div align="center">

<img src="app/assets/icon.png" width="128" alt="Catagorize">

# Catagorize

**特定文件夹整理工具：体检 / 规则整理 / 指纹去重 / 全文检索**

文件**原地不动**，工具围着文件转。受管目录随时脱离本软件照常使用，
不导入、不复制、零锁定。

</div>

## 与"资料库类"工具的区别

传统资料库工具把文件复制进自己的库，文件脱离原工作位置、
产生副本、被格式锁定。Catagorize 反着来：

- **文件系统即数据库**：整理 = 在目录内移动文件，目录本身就是成果
- **索引与配置全部在用户配置目录**（`platformdirs`），受管目录保持干净
- **永不删除**：只有「移动」和「移入隔离区」两种动作，隔离也是移动
- **先预览后执行**：所有整理先出 dry-run 计划，冲突在计划期就暴露
- **一键撤销**：每个动作先记日志再动手，逆序回滚

## 两种画像模式

| 模式 | 适用 | 行为 |
|---|---|---|
| `flow` 流入型 | 下载目录、桌面 | 规则引擎 + 目录监听，新文件落盘自动归类（防抖 2 秒） |
| `archive` 存量型 | 项目资料库 | 体检报告 + 内容级去重 + 全文检索 |

## 架构

```
app/
├─ core/        # 领域层（零 GUI 依赖，UI / 未来 CLI 共用）
│   ├─ models.py        # FolderProfile / Rule / FileRecord / Plan
│   ├─ scanner.py       # 只读体检扫描
│   ├─ fingerprint.py   # SHA-256 分块指纹
│   ├─ rules.py         # 规则匹配（priority 升序，先命中先生效）
│   ├─ planner.py       # dry-run 计划（去重 + 冲突检测，只读）
│   ├─ executor.py      # 执行 + 操作日志 + 撤销
│   └─ store.py         # 画像 JSON 持久化 + SQLite(WAL) 索引/日志
├─ services/    # 应用层：QThread 任务 / 目录监听 / 系统通知
├─ ui/          # 表现层：FluentWindow + Mica（PySide6-Fluent-Widgets）
└─ main.py      # GUI 入口（单实例 / 崩溃钩子 / 主题）
```

核心约定（继承自对 DropDesk 的逆向结论）：

- 根目录丢失 → 抛 `RootMissingError`，**绝不自动重建**空目录顶替
- 模糊文件一律不动：无规则命中 = 留在原地
- 文件名冲突、目标被占用 → `PlanConflictError` 在预览期报错，不留到执行期

## 开发

```bash
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 跑 core 层测试（无需 GUI 依赖）
.venv\Scripts\python.exe -m pytest tests/ -q

# 启动 GUI
.venv\Scripts\python.exe -m app.main
```

打包：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_nuitka.ps1`
（先跑测试，Nuitka standalone 编译，产物用 Inno Setup 打开 `installer\catagorize.iss` 出安装包）

exe 旁放置 `portable.flag` 启用便携模式（数据写入 `CatagorizeData/`）。

## 路线图

- [ ] 体检报告 UI（类型分布 / 体积 Top / 重复组 / 垃圾文件）
- [ ] 规则编辑器（文件夹页内）
- [ ] dry-run 预览清单 + 确认执行 + 撤销按钮
- [ ] 流入型画像的监听自动归类
- [ ] 文件内容全文索引（FTS5 虚表已就位）
- [ ] Windows.Media.Ocr 内容级检索
- [ ] 自动更新
