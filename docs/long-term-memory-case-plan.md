# 长期记忆 Case 实施计划

## 目标

让 Case v2 自包含用户画像、长期 Timeline 记忆和多轮提问。每次执行先租用并清空
cx-agent 专用测试账号，再原子写入 Case 的初始化数据，最后使用真实多轮会话和统一
八维/指南 Judge 评分。

## 数据流

1. `TestCase.initial_state` 严格校验画像与 Timeline 记忆。
2. Runner 把初始化数据写入 `ChatRequest.metadata`。
3. `CxAgentAdapter` 首轮租号时把初始化数据提交给 cx-agent。
4. cx-agent 清空账号后写入基础画像、医疗档案和 Timeline，并把动态 `facts` 绑定到租约。
5. cx-agent 测试聊天加载真实 `MemoryManager` 上下文，同时把动态 `facts` 作为数据块注入
   第二条 system message；多轮继续复用同一个 Session。
6. Judge 同时读取完整对话和 Case 初始化真值，判断事实召回、对象归属和回答准确性。

评测账号分成两个资源池：原 `101～103` 继续服务普通 Case，新 `201～203` 仅服务
`initial_state` Case。账号不是永久绑定 Case：同一 Case 的全部轮次独占一个租约；结束后
释放，下一 Case 租用时再次清空并按自身数据重新注入。

## 验收

- 普通 Case 不填写 `initial_state` 时行为不变。
- 非法画像字段、记忆分类、日期和分值在加载阶段失败。
- 初始化数据只随租号请求发送一次，不随每轮聊天重复写入。
- 两轮以上对话复用同一 cx-agent Session。
- cx-agent 测试路由的第二条 system message 包含画像与 Timeline 索引。
- MME 与 cx-agent 的定向测试、类型检查和构建全部通过。
