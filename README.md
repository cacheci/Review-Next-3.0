### TODO
- 整理代码结构
- 给回调数据加入 v3 前缀以方便共存
- 给被 ban 用户留申诉渠道
- 悄悄地 ban 人。
- 尝试发送消息使其会知道自己被解封
- 拒绝时忽略此投稿
- 拒绝时忽略此投稿并 ban
- `/stats` `/list_ban` `/reviewer_stats`
- `/help` 的实质内容
- 是否限制只能由原拒稿人选择拒稿理由

### 可用指令
#### 管理员：
`/update` 从 git 远端拉取最新源代码并运行。

`/become_reviewer` 在审核群中登记为审核。

`/ban` 字面意思，ban 人。***(WIP) 给被 ban 用户留申诉渠道。***

`/ban_noreply` ***(WIP) 悄悄地 ban 人。***

`/unban` 解封用户。***(WIP) 将尝试发送消息使其会知道自己被解封。***

`/list_ban` ***(WIP)***

`/reviewer_stats` ***(WIP)***

#### 用户
`/help` 查看帮助（当前与 `/start` 功能相同）

`/stats` ***(WIP)***


### 项目结构
```plaintext
├── main.py
├── database
│   ├── posts.db
│   └── users.db
└── src
    ├── __init__.py
    ├── bot
    │   ├── __init__.py
    │   ├── callback
    │   │   ├── __init__.py    //
    │   │   ├── inline.py      // inline
    │   │   ├── review.py      // 审核
    │   │   ├── submit.py      // 确认投稿
    │   │   └── users.py       // 取消投稿
    │   ├── command
    │   │   ├── __init__.py    //
    │   │   ├── admin.py       // 审核用的指令
    │   │   └── user.py        // 用户用的指令
    │   └── message.py         // 处理投稿
    ├── config.py
    ├── database               // 数据库相关
    │   ├── __init__.py
    │   ├── backup.py
    │   ├── posts.py
    │   └── users.py
    ├── logger.py              // 日志记录器
    ├── scheduler
    │   ├── __init__.py
    │   └── clean.py
    └── utils.py               // 也是审核
```