# pram_lifecontroler

## 功能

### 1. 中国大学MOOC 作业检测 (`webtask.py`)
- 自动检测课程作业、测验、互评、考试
- 变更追踪：新增/分数变化/状态变化
- 支持忽略类型（如忽略随堂测验）
- QQ邮箱通知

### 2. NEU 数学机考选位监控 (`seathehero.py`)
- 自动登录选位系统
- 监控目标机房开放状态
- 余座变化实时推送
- QQ邮箱通知

### 3. 总控台 (`run.py`)
- 交互式菜单，按需启动功能
- 首次运行引导配置

## 快速开始

```bash
pip install requests selenium
python run.py
```

## 配置

| 文件 | 说明 |
|---|---|
| `config/cookie` | MOOC 登录 Cookie（自动弹窗登录可不填） |
| `config/aimLesson` | MOOC 课程 URL |
| `config/notify` | SMTP 邮件通知 |
| `config/mathe_auth` | NEU 选位系统学号密码 |
| `config/mathe_target` | 选位监控目标 |
| `config/ignore` | 忽略的任务类型 |

配置模板见 `config/*.example` 文件。

## 项目结构

```
pram_lifecontroler/
├── run.py            # 总控台入口
├── webtask.py        # MOOC 作业检测
├── seathero.py       # NEU 选位监控
├── config/           # 配置文件（含 .example 模板）
├── log/              # 日志输出
└── NEUseathero/      # 原版 PowerShell 脚本
```
