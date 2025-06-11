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

# 引入 logger
from astrbot.logger import logger

@register("kcbxt", "teheiw192", "课程表提醒插件", "1.0.0", "https://github.com/teheiw192/kcbxt")
class KCBXTPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.gallery_dir = os.path.join(self.data_dir, "galleries")
        self.gallery_info_file = os.path.join(self.data_dir, "gallery_info.json")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.gallery_dir, exist_ok=True)

        # 初始化图库管理器
        self.default_gallery_info = {
            "name": "local",
            "path": os.path.join(self.gallery_dir, "local"),
            "creator_id": "127001",
            "creator_name": "local",
            "capacity": 200,
            "compress": True,
            "duplicate": True,
            "fuzzy": False,
        }
        self.gm = GalleryManager(self.gallery_dir, self.gallery_info_file, self.default_gallery_info)

        # 启动定时提醒任务
        asyncio.create_task(self.reminder_loop())

    @filter.command("kcbxt")
    async def show_table(self, event: AstrMessageEvent):
        """展示用户的课程表"""
        user_id = event.get_sender_id()
        table_path = os.path.join(self.data_dir, f"{user_id}.json")
        if not os.path.exists(table_path):
            yield event.plain_result("你还没有上传课程表，请发送Word或图片格式的课程表。")
            return
        with open(table_path, "r", encoding="utf-8") as f:
            table = json.load(f)
        msg = "你的课程表：\n"
        for c in table["courses"]:
            msg += f"{c['course']} {c['time']} {c['location']} {c['teacher']}\n"
        yield event.plain_result(msg)

    @filter.command("kcbxt today")
    async def show_today(self, event: AstrMessageEvent):
        """展示用户当天课程"""
        user_id = event.get_sender_id()
        table_path = os.path.join(self.data_dir, f"{user_id}.json")
        if not os.path.exists(table_path):
            yield event.plain_result("你还没有上传课程表，请发送Word或图片格式的课程表。")
            return
        with open(table_path, "r", encoding="utf-8") as f:
            table = json.load(f)
        today = get_today_weekday()
        msg = f"你今天({today})的课程：\n"
        found = False
        for c in table["courses"]:
            if today in c['time']:
                msg += f"{c['course']} {c['time']} {c['location']} {c['teacher']}\n"
                found = True
        if not found:
            msg += "今天没有课程！"
        yield event.plain_result(msg)

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE | EventMessageType.PRIVATE_MESSAGE)
    async def on_file_or_image(self, event: AstrMessageEvent, *args, **kwargs):
        """监听群聊和私聊消息，自动识别Word/图片/Excel并解析课程表"""
        from astrbot.api.message_components import File, Image
        ocr_api_url = getattr(self, 'config', {}).get('ocr_api_url')
        ocr_api_key = getattr(self, 'config', {}).get('ocr_api_key')
        for comp in event.get_messages():
            if isinstance(comp, (File, Image)):
                file_url = comp.file
                file_name = getattr(comp, "name", "") or os.path.basename(file_url)
                ext = os.path.splitext(file_name)[-1].lower()
                user_id = event.get_sender_id()
                save_path = os.path.join(self.data_dir, f"{user_id}{ext}")
                try:
                    # 下载或复制文件到本地
                    await download_file(file_url, save_path)
                    
                    if ext in [".docx", ".doc"]:
                        courses = parse_word(save_path)
                    elif ext in [".xlsx"]:
                        courses = parse_xlsx(save_path)
                    elif ext in [".jpg", ".jpeg", ".png", ".bmp"]:
                        if not ocr_api_url:
                            await event.send(event.plain_result("请在插件后台配置图片识别API接口！"))
                            return
                        courses = await parse_image(save_path, ocr_api_url, ocr_api_key)
                    else:
                        await event.send(event.plain_result("暂不支持该文件类型，仅支持Word、Excel或图片格式的课程表！"))
                        return
                    data = {
                        "courses": courses,
                        "unified_msg_origin": event.unified_msg_origin
                    }
                    with open(os.path.join(self.data_dir, f"{user_id}.json"), "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    await event.send(event.plain_result("课程表解析并保存成功！"))
                except Exception as e:
                    error_msg = f"处理课程表时发生错误: {e}"
                    await event.send(event.plain_result(f":( {error_msg}")) # 用户友好提示
                    logger.error(f"[KCBXT] {error_msg}\n{traceback.format_exc()}") # 详细日志用于调试
                return
        pass

    @filter.event_message_type(EventMessageType.PLAIN_MESSAGE)
    async def on_plain_message(self, event: AstrMessageEvent, *args, **kwargs):
        """监听纯文本消息，尝试解析课程表文字"""
        text_content = event.get_plain_text()
        if not text_content:
            return
        
        # 检查是否是指令消息，避免重复处理
        if text_content.startswith("/"):
            return

        # 尝试解析课程表文字
        user_id = event.get_sender_id()
        try:
            courses = parse_text_schedule(text_content)
            if courses:
                data = {
                    "courses": courses,
                    "unified_msg_origin": event.unified_msg_origin
                }
                with open(os.path.join(self.data_dir, f"{user_id}.json"), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                await event.send(event.plain_result("课程表文字解析并保存成功！请使用 \"kcbxt\" 命令查看。" + "(注意：纯文本解析可能不完全准确，请核对。)"))
            else:
                await event.send(event.plain_result("未能从文本中识别出课程表信息，请尝试以下格式：课程名 时间 地点 老师"))
        except Exception as e:
            error_msg = f"处理课程表文字时发生错误: {e}"
            await event.send(event.plain_result(f":( {error_msg}"))
            logger.error(f"[KCBXT] {error_msg}\n{traceback.format_exc()}")
        return

    async def reminder_loop(self):
        """定时检查并提醒所有用户"""
        while True:
            await self.check_and_remind()
            await asyncio.sleep(60)  # 每分钟检查一次

    async def check_and_remind(self):
        """检查所有用户，是否有课程需要提醒"""
        now = datetime.datetime.now()
        today = get_today_weekday()
        for file in os.listdir(self.data_dir):
            if file.endswith(".json"):
                with open(os.path.join(self.data_dir, file), "r", encoding="utf-8") as f:
                    table = json.load(f)
                unified_msg_origin = table.get("unified_msg_origin")
                for c in table["courses"]:
                    # 假设时间字段格式如"周一第1-2节"
                    if today in c['time']:
                        # 假设上课时间为08:00，实际可扩展为解析具体时间
                        class_time = get_class_time_from_str(c['time'])
                        if class_time:
                            class_dt = now.replace(hour=class_time[0], minute=class_time[1], second=0, microsecond=0)
                            delta = (class_dt - now).total_seconds()
                            if 0 < delta <= 600 and unified_msg_origin:  # 提前10分钟提醒
                                await self.context.send_message(unified_msg_origin, [f"上课提醒：{c['course']} {c['time']} {c['location']} {c['teacher']}"])

    # 图库相关功能
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

        yield event.plain_result("请发送要保存的图片")

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

        index = int(args[2]) if len(args) > 2 else None
        result = gallery.delete_image(index)
        yield event.plain_result(result)

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

        index = int(args[2]) if len(args) > 2 else None
        image_path = gallery.get_image(index)
        if image_path:
            yield event.image_result(image_path)
        else:
            yield event.plain_result("未找到图片")

    @filter.command("图库列表")
    async def list_galleries(self, event: AstrMessageEvent):
        """列出所有图库"""
        if not self.gm.galleries:
            yield event.plain_result("暂无图库")
            return

        msg = "【图库列表】\n"
        for gallery in self.gm.galleries.values():
            msg += f"图库名：{gallery.name}\n"
            msg += f"创建者：{gallery.creator_name}\n"
            msg += f"图片数量：{len(os.listdir(gallery.path))}\n"
            msg += f"容量：{gallery.capacity}\n"
            msg += "-------------------\n"
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
        msg = f"【图库详情】\n"
        msg += f"图库名：{info['name']}\n"
        msg += f"创建者：{info['creator_name']}\n"
        msg += f"图片数量：{info['image_count']}\n"
        msg += f"容量：{info['capacity']}\n"
        msg += f"压缩：{'开启' if info['compress'] else '关闭'}\n"
        msg += f"去重：{'开启' if info['duplicate'] else '关闭'}\n"
        msg += f"匹配模式：{'模糊' if info['fuzzy'] else '精准'}\n"
        msg += f"关键词：{', '.join(info['keywords'])}"
        yield event.plain_result(msg)

    async def _download_file(self, url: str) -> bytes:
        """下载文件"""
        if url.startswith("http://") or url.startswith("https://"):
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    return await resp.read()
        else:
            if os.path.exists(url):
                with open(url, "rb") as f:
                    return f.read()
            raise FileNotFoundError(f"文件不存在: {url}")

def get_today_weekday():
    # 返回如"周一"
    week_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return week_map[datetime.datetime.now().weekday()]

def get_class_time_from_str(time_str):
    # 简单示例：如"08:00"或"第1-2节"映射为08:00
    # 实际可根据学校作息表自定义
    if "第1-2节" in time_str:
        return (8, 0)
    if "第3-4节" in time_str:
        return (10, 0)
    if "第5-6节" in time_str:
        return (14, 0)
    if "第7-8节" in time_str:
        return (16, 0)
    return None

async def download_file(url, save_path):
    if url.startswith("http://") or url.startswith("https://"):
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                with open(save_path, "wb") as f:
                    f.write(await resp.read())
    else:
        if os.path.exists(url):
            shutil.copy(url, save_path)
        else:
            raise FileNotFoundError(f"文件处理失败：本地文件不存在或无法直接访问: {url}。可能需要配置对应平台的API来下载文件。") 