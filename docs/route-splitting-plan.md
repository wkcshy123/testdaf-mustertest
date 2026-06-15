# Web 路由拆分方案

## 目标

- 降低 `testdaf_platform/web.py` 的职责密度，避免入口文件继续膨胀。
- 保持现有 URL、模板表单 action、重定向目标不变，先做结构迁移，不改变业务行为。
- 为后续拆分 usecase、存储服务和导出服务预留清晰边界。

## 当前路由分组

### 基础与公共路由

- `GET /`
- `GET /health`
- `GET /student`
- `GET /jobs/{job_id}`
- 静态挂载：`/static`、`/question-bank`

建议模块：`routers/core.py`、`routers/jobs.py`、`routers/student.py`。

### 老师首页

- `GET /teacher`

建议模块：`routers/teacher_dashboard.py`。

### 题库管理

- `GET /teacher/manage/trash`
- `GET /teacher/manage/{section}`
- `POST /teacher/manage/delete`
- `POST /teacher/manage/restore`
- `POST /teacher/manage/rename`
- `GET /teacher/manage/download/{fmt}`

建议模块：`routers/teacher_manage.py`。

注意：`/teacher/manage/trash` 必须注册在 `/teacher/manage/{section}` 之前，避免被动态路由误匹配。

### 听力出题

- `GET /teacher/listening/aufgabe-1`
- `GET /teacher/listening/aufgabe-2`
- `GET /teacher/listening/aufgabe-3`
- `POST /teacher/listening/create`
- `POST /teacher/listening/aufgabe-2/create`
- `POST /teacher/listening/aufgabe-3/create`

建议模块：`routers/teacher_listening.py`。

注意：`POST /teacher/listening/create` 是 Aufgabe 1 的既有路径，拆分时必须保留，避免破坏当前模板。

### 阅读出题

- `GET /teacher/reading/aufgabe-1`
- `GET /teacher/reading/aufgabe-2`
- `GET /teacher/reading/aufgabe-3`
- `POST /teacher/reading/aufgabe-1/create`
- `POST /teacher/reading/aufgabe-2/create`
- `POST /teacher/reading/aufgabe-3/create`

建议模块：`routers/teacher_reading.py`。

### 写作出题

- `GET /teacher/writing/aufgabe-1`
- `POST /teacher/writing/aufgabe-1/create`

建议模块：`routers/teacher_writing.py`。

### 口语出题

- `GET /teacher/speaking/test-set`
- `POST /teacher/speaking/test-set/create`
- `GET /teacher/speaking/aufgabe-{number}`
- `POST /teacher/speaking/aufgabe-{number}/create`

建议模块：`routers/teacher_speaking.py`。

注意：`/teacher/speaking/test-set` 必须注册在 `/teacher/speaking/aufgabe-{number}` 之前。

## 拆分顺序

1. 先拆 `teacher_manage.py`，因为它和出题生成流程耦合最少。
2. 再拆 `jobs.py`、`student.py`、`teacher_dashboard.py`，这些路由逻辑较薄。
3. 然后按模块拆 `teacher_listening.py`、`teacher_reading.py`、`teacher_writing.py`、`teacher_speaking.py`。
4. 最后再把各 POST 创建流程从 router 迁移到 `usecases/`，避免 router 只换文件但业务编排仍过重。

## 依赖注入策略

- 短期：保留现有全局服务实例，通过 `app.state` 或 router factory 传入。
- 中期：新增 `create_app()`，在应用装配阶段创建服务，并通过 FastAPI dependency 获取。
- 长期：把题库、导出、LLM、TTS、后台任务抽象成接口，便于测试和替换实现。

## 验收清单

- 所有旧 URL 保持可访问。
- 所有模板中的 `href` 和 `action` 不需要同步改动。
- `GET /teacher/manage/trash` 不被 `GET /teacher/manage/{section}` 吞掉。
- `GET /teacher/speaking/test-set` 不被动态口语题路由吞掉。
- `uv run python -m compileall testdaf_platform` 通过。
- 启动后 FastAPI 路由清单和拆分前一致。
