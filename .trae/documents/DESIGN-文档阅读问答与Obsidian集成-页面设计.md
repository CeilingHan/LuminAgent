# 页面设计说明（桌面优先）

## 全局设计
- Layout：桌面端采用三栏/两栏混合（左侧工具与目录、中心预览、右侧聊天）；CSS Grid 为主，局部 Flex。≥1280px 为三栏；<1024px 收敛为上下布局（预览在上、聊天在下），左侧栏折叠为抽屉。
- Meta（默认）：
  - Title：文档阅读问答
  - Description：上传 PDF/Word 预览，边读边问，并一键保存到 Obsidian。
  - OG：og:title=同 Title，og:description=同 Description
- Global Styles（Tokens）：
  - 背景：#0B1220；卡片：#111A2E；边框：rgba(255,255,255,.08)
  - 文字：主色 #E6EDF7；次级 #9FB0CC
  - 主按钮：#3B82F6；Hover：#2563EB；危险：#EF4444
  - 字体：系统字体；字号：12/14/16/20/24；行高 1.5
  - 链接：#60A5FA；Hover 下划线
  - 交互：按钮/卡片 150ms ease；焦点态 2px #60A5FA

---

## 1) 阅读问答页（/）
### Meta
- Title：阅读问答｜文档阅读问答
- Description：上传 PDF/Word，预览并选区提问；回答可一键写入 Obsidian。

### Page Structure
- 顶部：App Header（左：产品名；中：当前文件名/页码；右：设置入口、连接状态灯）
- 主体：Desktop 三栏 Grid
  - Left：文档工具栏 +（可选）命中列表
  - Center：文档预览区
  - Right：聊天与保存区

### Sections & Components
1. Header
   - 连接状态：显示 Obsidian “已连接/未连接/只读/可写”徽标；点击跳转设置页。
   - 设置按钮：进入 Obsidian 连接设置页。

2. Left Panel（工具与检索）
   - 文件区：Upload 按钮（支持拖拽）；格式提示“PDF/.docx”。
   - 文档搜索：输入框 + 上一处/下一处按钮；显示命中数量；命中列表点击跳转（PDF=页码跳转，Word=滚动定位）。
   - Obsidian 增强开关：
     - Toggle「从 Obsidian 检索」
     - 结果摘要区：展示本次检索的 3–5 条 snippet（标题、路径、片段），可一键“复制引用”。

3. Center Panel（预览）
   - PDF：工具条（缩放、页码输入、上一页/下一页）。
   - Word：滚动容器；基础排版（标题、列表、加粗、引用）。
   - 选区浮层：选中文本后出现浮动按钮「引用并提问」，点击后把选区填入聊天输入上方的“引用块”。
   - 状态：加载 skeleton、失败重试、空态（引导上传）。

4. Right Panel（聊天与保存）
   - 引用块：展示当前引用（可删除/折叠）。
   - Chat Thread：用户与 AI 气泡；每条 AI 回复带工具条：复制、保存到 Obsidian。
   - 输入区：多行输入框 + 发送按钮；支持 Enter 发送（Shift+Enter 换行）。
   - 保存弹窗（点击“保存到 Obsidian”）：
     - 模式：新建笔记 / 追加到现有
     - 目标：路径选择（下拉/可输入）、标题（新建时必填）
     - 内容预览：默认包含回答正文 +（可选）来源引用（文档/Obsidian）
     - 权限提示：若当前为只读，按钮置灰并引导去设置页开启写入。

---

## 2) Obsidian 连接设置页（/settings/obsidian）
### Meta
- Title：Obsidian 设置｜文档阅读问答
- Description：配置并测试 Obsidian 连接，设置读/搜/写范围与权限。

### Page Structure
- 单列居中卡片（max-width 920px），分为“连接配置”“测试面板”“权限与范围”。

### Sections & Components
1. 连接配置 Card
   - API 地址输入（示例占位：http://127.0.0.1:xxxx）
   - 访问令牌/密钥输入（password 类型）
   - 按钮：保存、清除
   - 文案：说明数据仅保存在本地浏览器存储。

2. 测试面板 Card
   - Button「测试连接」
   - 测试项列表（逐项显示通过/失败与错误信息）：
     - 列出 Vault/根信息（若 API 支持）
     - 搜索一个关键字（例如 test）
     - 读取一篇指定路径笔记（可选输入）
     - 写入测试内容（需要开启写入后才可执行）

3. 权限与范围 Card
   - 写入模式：默认只读；开关「允许写入」（打开时二次确认）
   - 目录白名单：文本框（支持多行，每行一个路径前缀）
   - 行为提示：在阅读问答页写入时仍需要逐次确认。

4. Footer Actions
   - 返回阅读问答页按钮
