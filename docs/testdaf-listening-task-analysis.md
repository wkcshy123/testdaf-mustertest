# TestDaF 听力三大题题型分析与出题参数设计

## 文档目的

本文基于本地材料 `Modelltest_01_HV_Heft.pdf` 与 `Modelltest_01_HV_Transkription.pdf`，梳理 TestDaF 听力部分三个大题的结构、题型特征和出题系统所需参数。后续构建老师出题系统时，可将本文作为听力模块的题型设计依据。

## 总体结构

- TestDaF 听力部分包含 3 个听力文本，德语中标记为 `Hörtext 1`、`Hörtext 2`、`Hörtext 3`。
- 总时间为 40 分钟，其中包含最后 10 分钟答案誊写时间。
- `Hörtext 1` 和 `Hörtext 2` 各播放 1 遍。
- `Hörtext 3` 播放 2 遍。
- 作答形式混合使用简短文字答案与正误判断。
- 题目顺序严格跟随音频信息流，学生主要在听的过程中完成作答。

## Hörtext 1：校园生活场景问答

### 基本形式

- 示例主题：音乐学习、校园偶遇、学习经历。
- 材料形式：两人对话。
- 场景类型：校园或大学相关的日常/半学术场景。
- 播放次数：1 遍。
- 题目数量：8 题，编号 1-8。
- 作答方式：简短文字答案，以 Stichwörter 形式记录。
- 题干形式：以 `Warum`、`Welchen`、`Was`、`Wodurch`、`Welche Aufgabe` 等问题形式出现。
- 答案要求：多数题只需一个信息点，部分题明确要求两个信息点或一个例子。

### 能力侧重点

- 捕捉具体事实信息。
- 理解人物身份、经历、动机、计划和评价。
- 从对话中提取简短答案，而不是做长篇总结。
- 识别题干中的限定要求，例如“必须说出两点”或“必须举一个例子”。

### 题目结构特征

- 通常有一个示例题 `(0)`，用于展示作答方式。
- 题目直接要求学生回答具体问题。
- 题目顺序与听力文本信息出现顺序基本一致。
- 可出现“一题多点”的答案要求。
- 答案一般不是完整句，而是关键词、短语或极短句。

### 文本结构特征

- 两名说话人轮流发言。
- 一般有明确的关系设定，例如学生与老师、学生与工作人员、学生与同学。
- 开头常用于建立场景和人物关系。
- 中段展开经历、原因、需求、建议、机会或程序说明。
- 结尾通常出现下一步行动、建议、机会或任务。

### 出题系统设计参数

- `task_id`：固定为 `listening_aufgabe_1`。
- `scenario`：老师唯一必填的核心输入，例如“学生在大学图书馆咨询借书规则和学习空间预约”。`title`、`topic`、具体人物身份与关系都由 LLM 根据场景生成。
- `reference_material`：老师可选输入，用于补充真实语料、关键词、背景设定或必须覆盖的信息点。
- `difficulty`：老师可选输入，用于影响语言复杂度、干扰信息密度和题目难度。
- `information_flow`：老师可选输入，只允许 `sequential` 或 `shuffled`。`sequential` 表示题目答案点基本按听力文本顺序出现；`shuffled` 表示允许局部打乱信息出现顺序，但仍需保持 TestDaF 听力的可听性和可答性。
- `speech_speed`：老师可选输入，用于后续音频生成，例如 slow、normal、fast。
- `title`：LLM 生成结果，用于题库展示和学生端标题。
- `topic`：LLM 归纳结果，用于题库检索和标签化。
- `speaker_count`：系统固定为 2。
- `speaker_roles`：LLM 生成结果，例如学生、教师、秘书、同学、工作人员；生成后应允许老师编辑。
- `relationship`：LLM 生成结果，例如师生、同学、申请者与工作人员；生成后应允许老师编辑。
- `register`：系统默认约束为日常自然但清晰。
- `question_count`：系统固定为 8。
- `answer_mode`：系统固定为简短文字答案。
- `answer_length`：系统固定为关键词/短语。
- `required_points_per_question`：LLM 生成结果，默认每题 1 个信息点，可自然生成少量 2 信息点题。
- `transcript`：LLM 生成结果，即完整听力原文。
- `questions`：LLM 生成结果，即 8 个问题。
- `answers`：LLM 生成结果，即标准答案与可接受变体。
- `evidence_spans`：LLM 生成结果，即每题答案在原文中的依据。
- `audio_play_count`：不属于出题系统参数，由学生答题系统根据题型固定控制为 1 遍。
- `requires_example`：不作为独立配置项；如果出现“请举一个例子”类题干，由 LLM 在题目生成阶段自然决定。
- `scoring_notes`：后续评分系统使用，第一版可由 LLM 基于答案变体生成。

### 适合 MVP 的最小字段

- `scenario`
- `reference_material`
- `difficulty`
- `information_flow`
- `speech_speed`
- `title`
- `topic`
- `speaker_roles`
- `relationship`
- `transcript`
- `questions`
- `answers`
- `evidence_spans`
- `audio_path`

## Hörtext 2：专题访谈正误判断

### 基本形式

- 示例主题：Assessment-Center 与现代人员选拔。
- 材料形式：主持人与两位专家/嘉宾的专题访谈。
- 场景类型：广播访谈、专题节目、专家讨论。
- 播放次数：1 遍。
- 题目数量：10 题，编号 9-18。
- 作答方式：判断陈述 `Richtig` 或 `Falsch`。
- 题干形式：每题是一条陈述，学生判断是否与听力内容一致。
- 答案记录方式：在答题卡上标记 R/F。

### 能力侧重点

- 理解较长访谈中的事实、观点和评价。
- 判断陈述是否被原文支持。
- 分辨近义改写、否定、程度变化和范围变化。
- 识别不同说话人的观点归属。

### 题目结构特征

- 有一个示例陈述 `(0)`。
- 每道题不是问题，而是判断型陈述。
- 陈述通常对应文本中的一个关键信息点。
- 可考察事实、历史背景、专家评价、优缺点、条件、结论。
- 错误项常通过偷换主体、夸大程度、否定方向或遗漏条件构造。

### 文本结构特征

- 通常有主持人导入主题。
- 至少包含一个专家，示例中有两位专业角色。
- 主持人负责推进话题，专家提供解释、评价、补充。
- 主题通常偏社会、教育、职业、学术或公共议题。
- 文本信息密度高于 Hörtext 1。

### 出题系统设计参数

- `task_id`：固定为 `listening_aufgabe_2`。
- `title`：题目标题，例如“Assessment-Center – eine moderne Form der Personalauswahl”。
- `topic`：专题主题。
- `format`：访谈或专题讨论。
- `speaker_count`：建议为 3，即主持人 + 两位嘉宾。
- `speaker_roles`：主持人、专家 A、专家 B。
- `expert_domains`：专家领域，例如心理学、人力资源、教育学、医学、社会学。
- `audio_play_count`：播放次数，固定为 1。
- `question_count`：题目数量，固定为 10。
- `answer_mode`：正误判断。
- `statement_count`：判断陈述数量，固定为 10。
- `true_false_balance`：正确/错误陈述比例。
- `distractor_strategy`：错误陈述生成策略，例如主体替换、程度夸大、因果颠倒、否定转换。
- `viewpoint_mapping`：题目对应哪位说话人的观点。
- `information_flow`：陈述对应信息在原文中的出现顺序。
- `difficulty`：难度等级，可影响陈述改写程度与干扰强度。
- `speech_speed`：语速。
- `voice_config`：按说话人配置音色。
- `transcript`：访谈原文。
- `statements`：判断陈述列表。
- `answers`：R/F 标准答案。
- `evidence_spans`：答案依据，对应原文片段或摘要。

### 适合 MVP 的最小字段

- `title`
- `topic`
- `expert_domains`
- `speaker_roles`
- `reference_material`
- `statements`
- `answers`
- `transcript`
- `audio_path`

## Hörtext 3：专家访谈信息提取

### 基本形式

- 示例主题：感冒、病毒、免疫、防护。
- 材料形式：主持人与专家的一对一访谈。
- 场景类型：科学/医学/学术知识访谈。
- 播放次数：2 遍。
- 题目数量：7 题，编号 19-25。
- 作答方式：简短文字答案，以 Stichwörter 形式记录。
- 题干形式：开放式信息提取问题。
- 答案要求：部分题要求两个理由、两个例子或一个例子。

### 能力侧重点

- 理解较复杂的说明性、解释性信息。
- 提取原因、机制、比较结果、后果、用途、建议。
- 在第二遍播放中补全或校正答案。
- 识别科学解释中的条件、限定和因果关系。

### 题目结构特征

- 有一个示例题 `(0)`。
- 题目数量少于 Hörtext 2，但每题信息量更高。
- 多个题目要求多个答案点。
- 题干常考察原因、比较、后果、用途、传播方式、建议理由。
- 题目顺序与文本内容顺序一致。

### 文本结构特征

- 主持人提出问题，专家进行较长解释。
- 专家发言长度明显大于主持人。
- 主题一般偏科学、研究、社会知识或学术常识。
- 文本包含因果解释、研究发现、比较和建议。
- 可自然分成若干问答段，每段对应 1-2 道题。

### 出题系统设计参数

- `task_id`：固定为 `listening_aufgabe_3`。
- `title`：题目标题，例如“Vorsicht, Virus!”。
- `topic`：学术/科普主题。
- `format`：专家访谈。
- `speaker_count`：建议固定为 2，即主持人 + 专家。
- `speaker_roles`：主持人、专家。
- `expert_domain`：专家领域，例如医学、环境科学、教育研究、心理学、社会学。
- `audio_play_count`：播放次数，固定为 2。
- `question_count`：题目数量，固定为 7。
- `answer_mode`：简短文字答案。
- `answer_length`：关键词/短语。
- `required_points_per_question`：每题要求的信息点数量，默认 1，可配置为 2。
- `requires_example`：是否要求举例。
- `question_function`：题目考察功能，例如原因、比较、后果、用途、方式、建议理由。
- `information_flow`：题目答案在文本中的出现顺序。
- `difficulty`：难度等级，可影响解释密度、术语数量、句子长度。
- `speech_speed`：语速。
- `voice_config`：按说话人配置音色。
- `transcript`：访谈原文。
- `questions`：问题列表。
- `answers`：标准答案与可接受变体。
- `evidence_spans`：答案依据，对应原文片段或摘要。
- `second_play_instruction`：第二遍播放前的提示语。

### 适合 MVP 的最小字段

- `title`
- `topic`
- `expert_domain`
- `speaker_roles`
- `reference_material`
- `questions`
- `answers`
- `transcript`
- `audio_path`

## 三个大题对比表

| 维度 | Hörtext 1 | Hörtext 2 | Hörtext 3 |
|---|---|---|---|
| 播放次数 | 1 遍 | 1 遍 | 2 遍 |
| 题目数量 | 8 | 10 | 7 |
| 材料形式 | 两人校园对话 | 主持人 + 多位嘉宾访谈 | 主持人 + 专家访谈 |
| 作答形式 | 简短文字答案 | Richtig/Falsch | 简短文字答案 |
| 场景类型 | 校园生活/学习相关 | 社会、职业、教育等专题 | 科普、学术、专家解释 |
| 信息密度 | 中等 | 较高 | 高 |
| 主要考点 | 具体事实、经历、动机、任务 | 判断陈述是否符合原文 | 原因、机制、比较、后果、建议 |
| 出题难点 | 控制答案简短且可评分 | 构造合理错误陈述 | 控制答案点数量与解释密度 |

## 出题系统统一数据结构建议

```json
{
  "id": "q_20260613_xxxxxx",
  "section": "listening",
  "task_type": "listening_aufgabe_1",
  "title": "题目标题",
  "topic": "主题",
  "scenario": "具体情境",
  "reference_material": "老师提供的参考素材",
  "audio": {
    "play_count": 1,
    "speech_speed": "normal",
    "voice_config": [
      {
        "speaker": "Speaker A",
        "role": "学生",
        "voice": "Cherry"
      }
    ],
    "audio_path": "audio.wav"
  },
  "transcript": {
    "format": "dialogue",
    "speaker_count": 2,
    "text": "听力原文"
  },
  "items": [
    {
      "number": 1,
      "prompt": "题干",
      "answer_mode": "short_text",
      "required_points": 1,
      "answer": ["标准答案"],
      "acceptable_variants": [],
      "evidence": "答案依据"
    }
  ],
  "metadata": {
    "difficulty": "B2-C1",
    "tags": [],
    "created_at": "ISO 时间",
    "version": 1
  }
}
```

## 老师出题表单字段建议

### 所有听力题通用字段

- [ ] 题目标题。
- [ ] 听力大题类型：Aufgabe 1、Aufgabe 2、Aufgabe 3。
- [ ] 主题。
- [ ] 参考素材。
- [ ] 难度。
- [ ] 标签。
- [ ] 语速。
- [ ] 音色配置。
- [ ] 是否生成音频。
- [ ] 是否生成题目。
- [ ] 是否生成答案解析。

### Aufgabe 1 额外字段

- [ ] 场景描述，作为老师唯一必填的核心输入。
- [ ] 参考素材，作为可选输入。
- [ ] 难度，作为可选输入。
- [ ] 信息流控制，只允许顺序或打乱。
- [ ] 语速，作为后续音频生成参数。
- [ ] 不要求老师填写题目标题、主题、说话人身份和人物关系，这些由 LLM 生成后供老师编辑。
- [ ] 不要求老师配置播放次数，播放次数由学生答题系统控制。
- [ ] 不要求老师配置是否包含例子型答案，题干要求由 LLM 根据整体题目结构生成。

### Aufgabe 2 额外字段

- [ ] 访谈主题领域。
- [ ] 嘉宾数量。
- [ ] 嘉宾身份/专业领域。
- [ ] 正误题数量。
- [ ] 正误比例。
- [ ] 错误陈述构造方式。
- [ ] 每题对应说话人。

### Aufgabe 3 额外字段

- [ ] 专家领域。
- [ ] 知识型主题。
- [ ] 每题考察功能：原因、比较、后果、用途、方式、建议。
- [ ] 多信息点题目数量。
- [ ] 第二遍播放提示语。

## 后续实现建议

- [ ] 先实现 `listening_aufgabe_1`，因为它与现有德语 TTS 工具最接近，且文本结构最简单。
- [ ] 为 `listening_aufgabe_1` 建立独立 schema。
- [ ] 老师后台先只要求输入场景，参考素材、难度、信息流和语速作为可选参数。
- [ ] 先生成对话 transcript，再生成 8 个问题和答案。
- [ ] LLM 同时生成题目标题、主题标签、说话人身份和人物关系，并允许老师编辑。
- [ ] 老师确认 transcript、问题和答案后，再调用 TTS 生成音频。
- [ ] 保存完整题目包，包括 `manifest.json`、`transcript.txt`、`questions.json`、`audio.wav`。
- [ ] 学生端按 `manifest.json` 渲染题目，播放音频并保存答案。
