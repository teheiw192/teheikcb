"""
课程表提醒插件（kcbxt）
- 支持用户上传课程表（Word文档或图片），自动解析并保存。
- 每天上课前十分钟自动提醒用户当天要上的课程、地点、老师。
- 支持多用户独立课程表。
- 支持本地图库管理功能。
"""
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType
from astrbot.api.star import Context, Star, register
import asyncio
import os
import json
import datetime
from .parser import parse_word, parse_image, parse_xlsx, parse_text_schedule
from .gallery import Gallery, GalleryManager
import shutil
import traceback
import random
from PIL import Image
import io
from datetime import datetime, timedelta
import locale
from typing import Dict, List, Optional
from astrbot.api import logger
import astrbot.api.message_components as Comp
from astrbot.core.pipeline import Pipeline

# 设置中文locale
try:
    locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'zh_CN')
    except:
        pass

# 课程消息模板
COURSE_TEMPLATE = """【姓名同学学年学期课程安排】

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

请留意课程周次及教室安排，合理规划学习时间！"""

# 课程提醒模板
REMINDER_TEMPLATE = """同学你好，待会有课哦
上课时间（节次和时间）：
课程名称
教师：老师姓名
上课地点：教室/场地"""

@register("teheikcb", "teheiw192", "课程提醒插件", "1.0.0", "https://github.com/teheiw192/teheikcb")
class CourseReminderPlugin(Star):
    def __init__(self, context: Context, config: Dict):
        super().__init__(context)
        self.config = config
        self.data_dir = os.path.join("data", "teheikcb")
        os.makedirs(self.data_dir, exist_ok=True)
        self.schedules: Dict[str, Dict] = {}  # 用户ID -> {courses: List[Dict], settings: Dict}
        self.reminder_tasks: Dict[str, asyncio.Task] = {}
        self.load_schedules()
        asyncio.create_task(self.check_reminders())

    async def parse_course_with_ai(self, text: str) -> Tuple[List[Dict], Dict]:
        """使用AI模型解析课程信息"""
        prompt = f"""请帮我解析以下课程表信息，提取出所有课程的基本信息和课程安排。
要求：
1. 提取基本信息：学校、班级、专业、学院
2. 提取每个课程的：星期、上课时间、课程名称、教师、上课地点、周次
3. 返回JSON格式，包含两个部分：
   - basic_info: 包含基本信息
   - courses: 包含课程列表，每个课程包含day, time, name, teacher, location, weeks字段

课程表信息：
{text}

请直接返回JSON格式的数据，不要有其他文字说明。"""

        try:
            # 使用AstrBot的AI模型
            pipeline = Pipeline()
            response = await pipeline.llm_request(prompt)
            if response and response.content:
                result = json.loads(response.content)
                return result.get("courses", []), result.get("basic_info", {})
        except Exception as e:
            logger.error(f"AI解析课程表失败: {e}")
        
        return [], {}

    def load_schedules(self):
        """加载所有用户的课程表"""
        schedule_file = os.path.join(self.data_dir, "schedules.json")
        if os.path.exists(schedule_file):
            try:
                with open(schedule_file, "r", encoding="utf-8") as f:
                    self.schedules = json.load(f)
            except Exception as e:
                logger.error(f"加载课程表失败: {e}")
                self.schedules = {}

    def save_schedules(self):
        """保存所有用户的课程表"""
        schedule_file = os.path.join(self.data_dir, "schedules.json")
        try:
            with open(schedule_file, "w", encoding="utf-8") as f:
                json.dump(self.schedules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存课程表失败: {e}")

    def get_user_settings(self, user_id: str) -> Dict:
        """获取用户设置"""
        if user_id not in self.schedules:
            self.schedules[user_id] = {
                "courses": [],
                "settings": {
                    "enable_reminder": True,
                    "reminder_time": self.config.get("reminder_time", 30),
                    "enable_daily_reminder": self.config.get("enable_daily_reminder", True)
                },
                "basic_info": {}
            }
        return self.schedules[user_id]["settings"]

    def format_course_time(self, time_str: str) -> str:
        """格式化课程时间"""
        if "第" in time_str and "节" in time_str:
            period = time_str.split("第")[1].split("节")[0]
            time_slots = self.config.get("time_slots", {})
            if period in time_slots:
                return f"{time_str}（{time_slots[period]}）"
        return time_str

    def parse_time_slot(self, time_str: str) -> Optional[Tuple[str, str]]:
        """解析课程时间段，返回开始时间和结束时间"""
        if "第" in time_str and "节" in time_str:
            period = time_str.split("第")[1].split("节")[0]
            time_slots = self.config.get("time_slots", {})
            if period in time_slots:
                start_time, end_time = time_slots[period].split("-")
                return start_time, end_time
        return None

    @filter.command("课程表")
    async def show_schedule(self, event: AstrMessageEvent):
        """显示课程表"""
        user_id = event.get_sender_id()
        if user_id not in self.schedules:
            yield event.plain_result("你还没有设置课程表哦！请发送课程表文本给我。")
            return

        courses = self.schedules[user_id].get("courses", [])
        basic_info = self.schedules[user_id].get("basic_info", {})
        if not courses:
            yield event.plain_result("你的课程表是空的！")
            return

        # 按星期分组
        days = {}
        for course in courses:
            day = course.get("day", "未知")
            if day not in days:
                days[day] = []
            days[day].append(course)

        # 构建消息
        message = "📚 你的课程表：\n\n"
        
        # 添加基本信息
        if basic_info:
            message += "【基本信息】\n"
            for key, value in basic_info.items():
                message += f"{key}：{value}\n"
            message += "\n"

        # 添加课程信息
        for day in ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]:
            if day in days:
                message += f"【{day}】\n"
                for course in days[day]:
                    message += f"时间：{self.format_course_time(course['time'])}\n"
                    message += f"课程：{course['name']}\n"
                    message += f"教师：{course['teacher']}\n"
                    message += f"地点：{course['location']}\n"
                    message += f"周次：{course['weeks']}\n\n"

        yield event.plain_result(message)

    @filter.command("今日课程")
    async def show_today_courses(self, event: AstrMessageEvent):
        """显示今日课程"""
        user_id = event.get_sender_id()
        if user_id not in self.schedules:
            yield event.plain_result("你还没有设置课程表哦！")
            return

        today = datetime.now().strftime("%A")
        today_cn = {
            "Monday": "星期一",
            "Tuesday": "星期二",
            "Wednesday": "星期三",
            "Thursday": "星期四",
            "Friday": "星期五",
            "Saturday": "星期六",
            "Sunday": "星期日"
        }[today]

        courses = [c for c in self.schedules[user_id].get("courses", []) if c.get("day") == today_cn]
        if not courses:
            yield event.plain_result(f"今天（{today_cn}）没有课程安排！")
            return

        message = f"📚 今日（{today_cn}）课程：\n\n"
        for course in courses:
            message += f"时间：{self.format_course_time(course['time'])}\n"
            message += f"课程：{course['name']}\n"
            message += f"教师：{course['teacher']}\n"
            message += f"地点：{course['location']}\n"
            message += f"周次：{course['weeks']}\n\n"

        yield event.plain_result(message)

    @filter.command("测试提醒")
    async def test_reminder(self, event: AstrMessageEvent):
        """测试课程提醒"""
        user_id = event.get_sender_id()
        if user_id not in self.schedules:
            yield event.plain_result("你还没有设置课程表哦！")
            return

        courses = self.schedules[user_id].get("courses", [])
        if not courses:
            yield event.plain_result("你的课程表是空的！")
            return

        # 发送测试提醒
        course = courses[0]  # 使用第一个课程作为测试
        message = REMINDER_TEMPLATE.replace("上课时间（节次和时间）：", f"上课时间：{self.format_course_time(course['time'])}")
        message = message.replace("课程名称", course['name'])
        message = message.replace("老师姓名", course['teacher'])
        message = message.replace("教室/场地", course['location'])

        yield event.plain_result(message)

    @filter.command("提醒设置")
    async def reminder_settings(self, event: AstrMessageEvent):
        """设置提醒选项"""
        user_id = event.get_sender_id()
        settings = self.get_user_settings(user_id)
        
        message = "📝 提醒设置：\n\n"
        message += f"1. 自动提醒：{'开启' if settings['enable_reminder'] else '关闭'}\n"
        message += f"2. 提醒时间：上课前 {settings['reminder_time']} 分钟\n"
        message += f"3. 每日提醒：{'开启' if settings['enable_daily_reminder'] else '关闭'}\n\n"
        message += "回复数字 1-3 修改对应设置，或回复其他内容退出设置。"
        
        yield event.plain_result(message)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """处理所有消息"""
        # 检查是否是图片或文件
        if event.message_obj.type in ["image", "file"]:
            template = """抱歉，我暂时不支持识别图片和文件。

请按照以下步骤操作：
1. 复制下方课程消息模板
2. 将课程表图片或文件发送给豆包
3. 让豆包生成课程表文本
4. 将生成的文本发送给我

【课程消息模板】

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

请留意课程周次及教室安排，合理规划学习时间！"""
            yield event.plain_result(template)
            return

        # 处理文本消息
        text = event.message_str.strip()
        if not text:
            return

        # 使用AI解析课程表
        try:
            courses, basic_info = await self.parse_course_with_ai(text)
            if not courses:
                yield event.plain_result("抱歉，我无法识别这个课程表格式。请确保按照模板格式发送。")
                return

            # 保存课程表
            user_id = event.get_sender_id()
            if user_id not in self.schedules:
                self.schedules[user_id] = {
                    "courses": [],
                    "settings": {
                        "enable_reminder": True,
                        "reminder_time": self.config.get("reminder_time", 30),
                        "enable_daily_reminder": self.config.get("enable_daily_reminder", True)
                    },
                    "basic_info": {}
                }
            
            self.schedules[user_id]["courses"] = courses
            self.schedules[user_id]["basic_info"] = basic_info
            self.save_schedules()

            # 发送确认消息
            yield event.plain_result("课程表已保存！\n\n请确认以下课程信息是否正确：")
            yield event.plain_result(text)
            yield event.plain_result("\n如果信息正确，系统将自动开启课程提醒功能。\n\n你可以使用以下命令：\n/课程表 - 查看完整课程表\n/今日课程 - 查看今日课程\n/测试提醒 - 测试课程提醒功能\n/提醒设置 - 设置提醒选项")

        except Exception as e:
            logger.error(f"解析课程表失败: {e}")
            yield event.plain_result("抱歉，我无法识别这个课程表格式。请确保按照模板格式发送。")

    async def check_reminders(self):
        """检查并发送课程提醒"""
        while True:
            try:
                now = datetime.now()
                
                # 检查每日提醒
                if self.config.get("enable_daily_reminder", True):
                    daily_time = self.config.get("daily_reminder_time", "23:00")
                    if now.strftime("%H:%M") == daily_time:
                        for user_id, data in self.schedules.items():
                            settings = data.get("settings", {})
                            if not settings.get("enable_daily_reminder", True):
                                continue
                                
                            tomorrow = (now + timedelta(days=1)).strftime("%A")
                            tomorrow_cn = {
                                "Monday": "星期一",
                                "Tuesday": "星期二",
                                "Wednesday": "星期三",
                                "Thursday": "星期四",
                                "Friday": "星期五",
                                "Saturday": "星期六",
                                "Sunday": "星期日"
                            }[tomorrow]

                            tomorrow_courses = [c for c in data.get("courses", []) if c.get("day") == tomorrow_cn]
                            if tomorrow_courses:
                                message = f"📚 明日（{tomorrow_cn}）课程安排：\n\n"
                                for course in tomorrow_courses:
                                    message += f"时间：{self.format_course_time(course['time'])}\n"
                                    message += f"课程：{course['name']}\n"
                                    message += f"教师：{course['teacher']}\n"
                                    message += f"地点：{course['location']}\n"
                                    message += f"周次：{course['weeks']}\n\n"
                                message += "是否开启明日课程提醒？回复\"是\"开启提醒。"

                                # 发送消息
                                await self.context.send_message(user_id, [Comp.Plain(message)])

                # 检查当前课程提醒
                if self.config.get("enable_auto_reminder", True):
                    for user_id, data in self.schedules.items():
                        settings = data.get("settings", {})
                        if not settings.get("enable_reminder", True):
                            continue
                            
                        reminder_time = settings.get("reminder_time", self.config.get("reminder_time", 30))
                        
                        for course in data.get("courses", []):
                            # 解析课程时间
                            time_slot = self.parse_time_slot(course['time'])
                            if time_slot:
                                start_time, _ = time_slot
                                # 检查是否需要提醒
                                course_time = datetime.strptime(start_time, "%H:%M").time()
                                reminder_time_obj = (datetime.combine(now.date(), course_time) - 
                                                   timedelta(minutes=reminder_time)).time()
                                
                                if now.time() == reminder_time_obj:
                                    message = REMINDER_TEMPLATE.replace("上课时间（节次和时间）：", f"上课时间：{self.format_course_time(course['time'])}")
                                    message = message.replace("课程名称", course['name'])
                                    message = message.replace("老师姓名", course['teacher'])
                                    message = message.replace("教室/场地", course['location'])

                                    # 发送提醒
                                    await self.context.send_message(user_id, [Comp.Plain(message)])

            except Exception as e:
                logger.error(f"检查课程提醒失败: {e}")

            await asyncio.sleep(60)  # 每分钟检查一次

    async def terminate(self):
        """插件终止时保存数据"""
        self.save_schedules()

    @filter.command("图库帮助")
    async def gallery_help(self, event: AstrMessageEvent):
        """显示图库帮助信息"""
        help_text = """【图库管理命令】
/图库帮助 - 显示此帮助信息
/存图 <图库名> [序号] - 保存图片到指定图库
/删图 <图库名> [序号] - 删除图库中的图片
/查看 <图库名> [序号] - 查看图库中的图片
/图库列表 - 查看所有图库
/图库详情 <图库名> - 查看图库详细信息
/精准匹配词 - 查看精准匹配词
/模糊匹配词 - 查看模糊匹配词
/模糊匹配 <图库名> - 将图库切换到模糊匹配模式
/精准匹配 <图库名> - 将图库切换到精准匹配模式
/添加匹配词 <图库名> <匹配词> - 为图库添加匹配词
/删除匹配词 <图库名> <匹配词> - 删除图库的匹配词
/设置容量 <图库名> <容量> - 设置图库容量
/开启压缩 <图库名> - 开启图库压缩
/关闭压缩 <图库名> - 关闭图库压缩
/开启去重 <图库名> - 开启图库去重
/关闭去重 <图库名> - 关闭图库去重
/去重 <图库名> - 去除图库中的重复图片"""
        yield event.plain_result(help_text)

    @filter.command("存图")
    async def add_image(self, event: AstrMessageEvent):
        """保存图片到图库"""
        args = event.get_plain_text().split()
        if len(args) < 2:
            yield event.plain_result("请指定图库名称")
            return

        gallery_name = args[1]
        gallery = self.gm.get_gallery(gallery_name)
        if not gallery:
            try:
                gallery = self.gm.create_gallery(
                    gallery_name,
                    event.get_sender_id(),
                    event.get_sender_name()
                )
            except Exception as e:
                yield event.plain_result(str(e))
                return

        # 获取图片
        for comp in event.get_messages():
            if hasattr(comp, "file"):
                try:
                    # 下载图片
                    image_data = await self._download_file(comp.file)
                    if not image_data:
                        yield event.plain_result("图片下载失败")
                        return

                    # 添加图片到图库
                    result = gallery.add_image(image_data)
                    yield event.plain_result(result)
                except Exception as e:
                    yield event.plain_result(f"保存图片失败: {str(e)}")
                return

    @filter.command("删图")
    async def delete_image(self, event: AstrMessageEvent):
        """删除图库中的图片"""
        args = event.get_plain_text().split()
        if len(args) < 2:
            yield event.plain_result("请指定图库名称")
            return

        gallery_name = args[1]
        gallery = self.gm.get_gallery(gallery_name)
        if not gallery:
            yield event.plain_result(f"图库【{gallery_name}】不存在")
            return

        try:
            if len(args) > 2:
                # 删除指定图片
                index = int(args[2])
                result = gallery.delete_image(index)
            else:
                # 清空图库
                result = gallery.delete_image()
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"删除图片失败: {str(e)}")

    @filter.command("查看")
    async def view_image(self, event: AstrMessageEvent):
        """查看图库中的图片"""
        args = event.get_plain_text().split()
        if len(args) < 2:
            yield event.plain_result("请指定图库名称")
            return

        gallery_name = args[1]
        gallery = self.gm.get_gallery(gallery_name)
        if not gallery:
            yield event.plain_result(f"图库【{gallery_name}】不存在")
            return

        try:
            if len(args) > 2:
                # 查看指定图片
                index = int(args[2])
                image_path = gallery.get_image(index)
            else:
                # 随机查看图片
                image_path = gallery.get_image()
            
            if image_path:
                yield event.image_result(image_path)
            else:
                yield event.plain_result(f"图库【{gallery_name}】中没有图片")
        except Exception as e:
            yield event.plain_result(f"查看图片失败: {str(e)}")

    @filter.command("图库列表")
    async def list_galleries(self, event: AstrMessageEvent):
        """列出所有图库"""
        galleries = self.gm.galleries
        if not galleries:
            yield event.plain_result("当前没有图库")
            return

        msg = "图库列表：\n"
        for name, gallery in galleries.items():
            info = gallery.get_info()
            msg += f"【{name}】- {info['image_count']}张图片\n"
        yield event.plain_result(msg)

    @filter.command("图库详情")
    async def gallery_details(self, event: AstrMessageEvent):
        """查看图库详细信息"""
        args = event.get_plain_text().split()
        if len(args) < 2:
            yield event.plain_result("请指定图库名称")
            return

        gallery_name = args[1]
        gallery = self.gm.get_gallery(gallery_name)
        if not gallery:
            yield event.plain_result(f"图库【{gallery_name}】不存在")
            return

        info = gallery.get_info()
        msg = f"图库【{gallery_name}】详情：\n"
        msg += f"创建者：{info['creator_name']}\n"
        msg += f"图片数量：{info['image_count']}\n"
        msg += f"容量上限：{info['capacity']}\n"
        msg += f"压缩：{'开启' if info['compress'] else '关闭'}\n"
        msg += f"去重：{'开启' if info['duplicate'] else '关闭'}\n"
        msg += f"模糊匹配：{'开启' if info['fuzzy'] else '关闭'}\n"
        if info['keywords']:
            msg += f"关键词：{', '.join(info['keywords'])}\n"
        yield event.plain_result(msg)

    async def _download_file(self, url: str) -> bytes:
        """下载文件"""
        try:
            async with self.context.http.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
                return None
        except Exception as e:
            logger.error(f"下载文件失败: {str(e)}")
            return None

def get_today_weekday():
    """获取今天的星期"""
    week_map = {
        'Monday': '星期一',
        'Tuesday': '星期二',
        'Wednesday': '星期三',
        'Thursday': '星期四',
        'Friday': '星期五',
        'Saturday': '星期六',
        'Sunday': '星期日'
    }
    return week_map.get(datetime.datetime.now().strftime('%A'), '未知')

def get_class_time_from_str(time_str: str) -> tuple:
    """从时间字符串解析上课时间"""
    try:
        # 解析时间字符串（格式：HH:MM-HH:MM）
        start_time = time_str.split('-')[0]
        hour, minute = map(int, start_time.split(':'))
        return (hour, minute)
    except:
        # 如果解析失败，返回默认时间
        return (8, 0)

async def download_file(url: str, save_path: str):
    """下载文件到指定路径"""
    try:
        async with self.context.http.get(url) as resp:
            if resp.status == 200:
                with open(save_path, 'wb') as f:
                    f.write(await resp.read())
                return True
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
    return False 