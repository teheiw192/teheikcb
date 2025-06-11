# 课程提醒插件 (teheikcb)

一个智能的课程提醒插件，支持文本格式的课程表识别和自动提醒功能。

## 仓库信息

- 仓库地址：[https://github.com/teheiw192/teheikcb](https://github.com/teheiw192/teheikcb)
- 作者：teheiw192
- 许可证：MIT License
- 版本：1.0.0

## 功能特点

- 📝 文本课程表识别
- ⏰ 自动课程提醒
- 📅 每日课程提醒
- ⚙️ 个性化提醒设置
- 📊 基本信息管理

## 安装说明

1. 在 AstrBot 插件市场中搜索 "课程提醒" 并安装
2. 或从 GitHub 克隆源码：
```bash
git clone https://github.com/teheiw192/teheikcb.git
```

## 使用说明

1. 发送课程表文本
   - 复制课程消息模板
   - 填写你的课程信息
   - 发送给机器人

2. 查看课程表
   - 使用 `/课程表` 命令查看完整课程表
   - 使用 `/今日课程` 命令查看今日课程

3. 提醒设置
   - 使用 `/提醒设置` 命令设置提醒选项
   - 使用 `/测试提醒` 命令测试提醒功能

## 提醒设置选项

1. 自动提醒
   - 开启/关闭自动提醒功能
   - 默认开启

2. 提醒时间
   - 设置课前提醒时间（分钟）
   - 默认30分钟

3. 每日提醒
   - 开启/关闭每日课程提醒
   - 默认开启

## 课程表格式

请按照以下格式发送课程表：

```
【姓名同学学年学期课程安排】

📚 基本信息

• 学校：XX大学（没有则不显示）
• 班级：XX班（没有则不显示）
• 专业：XX专业（没有则不显示）
• 学院：XX学院（没有则不显示）

🗓️ 每周课程详情
星期X

• 上课时间（节次和时间）：
课程名称
教师：老师姓名
上课地点：教室/场地
周次：具体周次

示例：
星期一
上课时间：第1-2节（08:00-09:40）
课程名称：如何找到富婆
教师：飘逸
上课地点150123
周次：1-16周

周末：无课程。

🌙 晚间课程

• 上课时间（节次和时间）：
课程名称
教师：老师姓名
上课地点：教室/场地
周次：具体周次

📌 重要备注

• 备注内容1
• 备注内容2

请留意课程周次及教室安排，合理规划学习时间！
```

## 注意事项

1. 提醒时间可以在设置中自定义
2. 每日提醒默认在23:00发送
3. 课程表数据保存在 `data/teheikcb/schedules.json` 中
4. 支持多用户管理

## 配置说明

插件配置文件 `_conf_schema.json` 包含以下选项：

- `reminder_time`: 课程提醒时间（分钟）
- `daily_reminder_time`: 每日提醒时间
- `enable_daily_reminder`: 是否启用每日提醒
- `enable_auto_reminder`: 是否启用自动提醒
- `time_slots`: 课程时间段配置

## 开发说明

### 项目结构

```
teheikcb/
├── main.py              # 主程序文件
├── _conf_schema.json    # 配置文件
├── metadata.yaml        # 插件元数据
├── requirements.txt     # 依赖包列表
└── README.md           # 说明文档
```

### 依赖包

- astrbot>=1.0.0
- python-dateutil>=2.8.2

### 开发环境

- Python 3.8+
- AstrBot 1.0.0+

## 贡献指南

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

## 许可证

MIT License

Copyright (c) 2024 teheiw192

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE. 