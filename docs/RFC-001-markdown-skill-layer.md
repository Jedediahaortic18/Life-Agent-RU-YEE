# RFC-001: Markdown Skill Layer (指令技能层)

> 状态: **Draft** | 阶段: **Phase 3 规划** | 日期: 2026-03-25

## 背景

LARY 当前的扩展体系基于 Python 代码插件（Plugin），每个扩展单元（Agent/Tool/Memory/Extension）都需要编写 Python 类并实现对应接口。这种方式功能强大，但门槛较高——用户无法在不写代码的情况下教 Agent 新的行为。

参考 OpenClaw 的 Skill 体系，我们计划在现有 Plugin 层之上增加一层 **Markdown Skill Layer**：用纯 Markdown 文件定义"指令技能"，让 Agent 学会组合使用已有 Tool 完成新任务，无需编写任何代码。

## 设计目标

1. **零代码扩展**: 用户只需编写一个 `SKILL.md` 文件即可教 Agent 新行为
2. **与现有 Plugin 共存**: Skill 层是 Plugin 层的补充，不替代
3. **低 Token 开销**: 按需注入相关 Skill，避免 prompt 膨胀
4. **热更新**: 修改 SKILL.md 后无需重启即可生效
5. **可分享**: 通过 SkillHub 市场分发纯 Markdown 技能包

## 核心概念

### Skill vs Plugin vs Tool 三层关系

```
┌─────────────────────────────────────────────┐
│  Skill Layer (Markdown 指令)                 │
│  "教 Agent 什么时候、怎么组合使用工具"         │
│  例: 健康饮食规划 skill → 组合 dish_query     │
│      + meal_recommend + shopping_list        │
├─────────────────────────────────────────────┤
│  Plugin Layer (Python 代码)                  │
│  Agent / Tool / Memory / Extension           │
│  例: meal_agent, DishQueryTool, ...          │
├─────────────────────────────────────────────┤
│  Core Framework                              │
│  orchestrator, intent_router, plugin_registry│
└─────────────────────────────────────────────┘
```

- **Tool**: 最小执行单元，Python 类，有 `execute()` 方法
- **Plugin**: 包含代码的完整模块（Agent/Memory/Extension），通过 manifest.yaml 声明
- **Skill**: 纯 Markdown 指令文件，描述何时触发、使用哪些 Tool、按什么流程执行

## SKILL.md 文件格式

```markdown
---
name: quick-purchase
description: 用户直接要求购买商品时，跳过菜谱规划，直接走采购流程
version: "1.0.0"
author: LARY
triggers:
  - "买*"
  - "采购*"
  - "下单*"
requires:
  tools:
    - address_get
    - address_save
    - agent_call
  agents:
    - purchasing_agent
tags: [购物, 采购, 盒马]
---

## 触发条件

用户消息中包含具体商品名称 + 购买意图词（买/采购/下单/加购物车）。

## 执行步骤

1. 复述用户要买的商品和数量，请用户确认
2. 调用 `address_get` 检查是否有收货地址
3. 如果没有地址，引导用户提供并调用 `address_save` 保存
4. 提醒用户采购可能耗时较长
5. 调用 `agent_call(target_agent="purchasing_agent", message="采购清单: ...")` 执行采购
6. 等待结果并向用户汇报

## 注意事项

- 不需要走菜谱推荐流程
- 采购清单应包含商品名和数量
- 如果用户要修改，回到步骤 1
```

### Frontmatter 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 技能标识符，snake_case |
| `description` | string | 是 | 一行描述，用于 Agent 判断是否使用该 Skill |
| `version` | string | 否 | 语义化版本号 |
| `author` | string | 否 | 作者 |
| `triggers` | list[string] | 否 | 触发模式（glob 通配符），辅助意图匹配 |
| `requires.tools` | list[string] | 否 | 依赖的 Tool 名称，加载时校验 |
| `requires.agents` | list[string] | 否 | 依赖的 Agent 名称 |
| `tags` | list[string] | 否 | 标签，用于市场搜索 |
| `user_invocable` | bool | 否 | 是否暴露为斜杠命令，默认 true |
| `priority` | int | 否 | 匹配优先级，默认 0 |

## 架构设计

### 加载流程

```
启动 / 热更新
    │
    ▼
SkillLoader.discover()
    │  扫描 skills/ 和 contrib/skills/ 目录
    │  解析 SKILL.md frontmatter
    │  校验 requires（依赖的 tool/agent 是否已注册）
    ▼
SkillRegistry
    │  name → SkillEntry 映射
    │  按 priority 排序
    ▼
就绪，等待查询
```

### 运行时匹配

```
用户消息
    │
    ▼
IntentRouter.route()
    │  1. 先走现有 Agent 路由（LLM 意图识别）
    │  2. 如果匹配到 Agent，检查该 Agent 是否有关联 Skill
    │  3. 如果有，将 Skill 指令注入到 Agent 的 system prompt
    ▼
Agent.run() ← system_prompt + 注入的 Skill 指令
    │
    ▼
Agent 按 Skill 指令组合调用 Tools
```

### 目录结构

```
skills/                          # 内置 Skill
  quick-purchase/
    SKILL.md
  healthy-meal-plan/
    SKILL.md
  weekly-menu/
    SKILL.md
contrib/skills/                  # 社区安装的 Skill
  custom-diet/
    SKILL.md
```

### 新增模块

| 模块 | 职责 |
|------|------|
| `core/skill_loader.py` | 发现、解析、校验 SKILL.md 文件 |
| `core/skill_registry.py` | Skill 注册表，提供查询接口 |
| `core/skill_injector.py` | 运行时将匹配的 Skill 注入 Agent prompt |

### 对现有模块的改动

| 模块 | 改动 |
|------|------|
| `core/orchestrator.py` | 调用 skill_injector 增强 Agent prompt |
| `core/intent_router.py` | 可选：利用 triggers 做预筛选加速 |
| `core/skillhub.py` | 支持 type=skill 的市场条目 |
| `api/skillhub.py` | 返回 Skill 列表和详情 |
| `web/src/views/SkillHubView.vue` | 增加"指令技能"分类 |

## 与 OpenClaw 的差异

| 维度 | OpenClaw Skill | LARY Skill (本方案) |
|------|---------------|-------------------|
| 文件格式 | SKILL.md + YAML frontmatter | 相同 |
| 依赖声明 | `requires.bins` / `requires.env` (系统级) | `requires.tools` / `requires.agents` (框架级) |
| 加载优先级 | workspace → 用户 → 内置 | skills/ → contrib/skills/ |
| 匹配方式 | 纯 LLM 判断 | triggers 预筛选 + LLM 判断 |
| 自进化 | Agent 可自己创建 Skill | Phase 3.2 考虑 |
| Token 管理 | 全量注入 prompt | 按需注入相关 Skill |

## 实施计划

### Phase 3.1: 基础 Skill 层 (MVP)

- [ ] `SkillLoader`: SKILL.md 解析 + frontmatter 校验
- [ ] `SkillRegistry`: 注册表 + 查询接口
- [ ] `SkillInjector`: 基于 Skill name 手动注入到 Agent prompt
- [ ] 将 meal_agent 的 system.j2 中部分规则抽取为 Skill (验证可行性)
- [ ] 单元测试覆盖

### Phase 3.2: 智能匹配 + 热更新

- [ ] triggers 模式匹配引擎
- [ ] LLM-based Skill 选择（多 Skill 时由 LLM 判断最相关的）
- [ ] 文件监听 (watchdog) 实现热更新
- [ ] Skill 间依赖和冲突检测

### Phase 3.3: 市场集成 + 自进化

- [ ] SkillHub 支持 type=skill 的发布/安装/卸载
- [ ] 前端 Skill 编辑器（Markdown 在线编辑 + 预览）
- [ ] Agent 自主创建 Skill 能力（对话中生成 SKILL.md）
- [ ] Skill 使用统计和效果评估

## 风险与注意事项

1. **Prompt 膨胀**: 注入过多 Skill 会增加 token 消耗和延迟，需要控制注入数量
2. **指令冲突**: 多个 Skill 对同一场景给出矛盾指令，需要优先级机制
3. **安全性**: 社区 Skill 可能包含恶意 prompt injection，需要审核机制
4. **调试困难**: Skill 注入后 Agent 行为不可预测，需要 Skill trace 日志
5. **与 Jinja2 模板的关系**: 现有 Agent 使用 Jinja2 模板作为 system prompt，Skill 注入需要与模板系统协调

## 参考

- [OpenClaw Skills 文档](https://docs.openclaw.ai/tools/skills.md)
- [OpenClaw Creating Skills](https://docs.openclaw.ai/tools/creating-skills.md)
- [ClawHub 技能市场](https://openclaw.ai/)
