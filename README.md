![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-1f6feb)
![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)

# 赛博算命 Skill

这是一个基于 [jinchenma94/bazi-skill](https://github.com/jinchenma94/bazi-skill) 的 OpenClaw 本地 fork。

在保留原始八字分析 workflow 的基础上，这个版本新增了 `scripts/bazi_cli.py` Python 排盘脚本，用来稳定计算四柱、大运和真太阳时相关上下文，避免纯手算带来的漂移。

## 功能

- **交互式信息收集**：逐步收集姓名、曾用名、阳历/农历生日、出生时辰、性别、出生地、在世状态等信息
- **Python 固定排盘**：优先调用 `scripts/bazi_cli.py` 计算四柱、大运、流年分析上下文，而不是手算
- **边界场景支持**：支持阳历/农历、未知时辰六字、仅提供时辰地支、早晚子时分日、真太阳时修正
- **经典命理分析**：结合《穷通宝典》《三命通会》《滴天髓》《渊海子平》《子平真诠》等典籍生成综合解读

## 与上游 fork 的差异

- 运行环境从 Claude Code 使用场景调整为 OpenClaw
- 新增 `scripts/bazi_cli.py` 和 `scripts/requirements.txt`
- `SKILL.md` 明确要求正式排盘优先走 Python 脚本
- README 与项目结构说明同步到了当前本地实现

## 安装位置

当前版本作为 OpenClaw 共享 skill 放在：

```bash
~/.openclaw/skills/bazi-skill
```

OpenClaw 会从 `~/.openclaw/skills` 自动发现共享 skill。

## 在 OpenClaw 中使用

输入以下任意关键词即可触发：

`算八字` `看八字` `批八字` `排八字` `四柱` `命盘` `算命` `排盘` `bazi`

触发后，skill 会先逐步确认出生信息，再调用 Python 脚本排盘，最后结合参考典籍做综合分析。

## Python 排盘脚本

### 依赖

要求 Python 3.11+。

```bash
cd ~/.openclaw/skills/bazi-skill
python3 -m pip install -r scripts/requirements.txt
```

### 调用方式

```bash
python3 scripts/bazi_cli.py --input /tmp/bazi_input.json --output /tmp/bazi_output.json
```

### 输入示例

```json
{
  "calendar_type": "solar",
  "time_input": "1990-05-15 12:00:00",
  "gender": "male",
  "location": {
    "timezone": "Asia/Shanghai",
    "city": "Dandong"
  }
}
```

### 支持的关键输入字段

- `calendar_type`：`solar` 或 `lunar`
- `time_input`：可传字符串，或 `{year, month, day, hour?, minute?, second?}` 对象
- `gender`：支持 `男/女`、`male/female`
- `time_unknown`：时辰未知时可退化为六字排盘，时柱留空
- `hour_branch`：只知道时辰地支时可直接传 `子` 到 `亥`
- `zi_hour_segment`：当 `hour_branch=子` 时必填，取值为 `night` 或 `early`
- `zi_hour_rule`：默认 `split-zi`，即早晚子时分日
- `use_true_solar_time`：启用真太阳时修正
- `longitude`：显式提供经度时优先使用
- `location.city` / `location.province` / `location.state` / `location.admin1` / `location.country`：未提供经度时，可用于在线 geocode 补经度

如果用户明确要求真太阳时，而且出生地可能重名，建议补全省份或国家，避免直接按模糊城市名入盘。

### 输出内容

脚本输出 JSON，主要包含这些区块：

- `normalized_input`：归一化后的输入
- `calendar`：阳历、农历、节气信息
- `bazi`：四柱、日主、胎元、命宫、身宫等结构化结果
- `luck`：大运相关结果
- `true_solar_time`：真太阳时修正细节
- `warnings`：输入或推算过程中的提示

## 参考典籍

| 典籍 | 简称 |
|------|------|
| 《穷通宝典》 | 论日主调候 |
| 《三命通会》 | 论格局神煞 |
| 《滴天髓》 | 论五行旺衰 |
| 《渊海子平》 | 论十神六亲 |
| 《千里命稿》 | 论命例实证 |
| 《协纪辨方书》 | 论择日神煞 |
| 《果老星宗》 | 论星命合参 |
| 《子平真诠》 | 论用神格局 |
| 《神峰通考》 | 论命理辨误 |

## 项目结构

```text
bazi-skill/
├── SKILL.md                        # Skill 入口与交互式分析流程
├── README.md
├── LICENSE
├── references/                     # 规则、表格、典籍摘要
│   ├── wuxing-tables.md
│   ├── shichen-table.md
│   ├── dayun-rules.md
│   └── classical-texts.md
└── scripts/
    ├── bazi_cli.py                 # Python 固定排盘脚本
    └── requirements.txt            # Python 依赖
```

## 免责声明

本 skill 仅供传统文化学习与娱乐参考，分析结果不构成任何医疗、法律、投资或人生决策依据。命理学属于传统文化范畴，请理性看待。
