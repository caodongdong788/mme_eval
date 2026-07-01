# Tasks

- [x] 1. Server TDD：飞书 Base URL 解析、分页记录读取、多轮 case 转换、上传 API 分流
- [x] 2. Server 实现：新增 Base 客户端与 benchmark 转换函数，复用现有上传存储/校验
- [x] 3. Frontend TDD：线上上传入口 URL/JSONL 复用、多轮预览
- [x] 4. Frontend 实现：选择「线上」时展示 URL 输入并更新文案，提交时后端分流
- [x] 5. 验证：相关 `pytest`、`cd frontend && npm run verify`、`openspec validate --strict`
- [x] 6. 审查与收尾：子 Agent ponytail-review、CodeRabbit 子 Agent（CLI 不可用，降级只读审查）、Graphify 结束刷新（缺 LLM API key 阻塞，已记录）、OpenSpec archive
