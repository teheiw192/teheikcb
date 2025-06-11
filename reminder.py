"""
课程提醒模块
负责定时检查和发送课程提醒
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Awaitable, Any
import locale

class CourseReminder:
    def __init__(self, data_dir: str, reminder_time: int = 10):
        """
        初始化课程提醒器
        
        Args:
            data_dir: 数据目录路径
            reminder_time: 提前提醒时间（分钟）
        """
        self.data_dir = data_dir
        self.reminder_time = reminder_time
        self.logger = logging.getLogger("CourseReminder")
        self.reminder_tasks: Dict[str, asyncio.Task] = {}
        self.callback: Optional[Callable[[str, List[Dict]], Awaitable[None]]] = None
        
        # 设置中文环境
        locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
        
        # 创建数据目录
        os.makedirs(data_dir, exist_ok=True)
        
        # 星期映射
        self.week_map = {
            'Monday': '星期一',
            'Tuesday': '星期二',
            'Wednesday': '星期三',
            'Thursday': '星期四',
            'Friday': '星期五',
            'Saturday': '星期六',
            'Sunday': '星期日'
        }

    def set_callback(self, callback: Callable[[str, List[Dict]], Awaitable[None]]):
        """设置提醒回调函数"""
        self.callback = callback

    async def start_reminder(self, user_id: str, schedule: List[Dict]):
        """启动提醒任务"""
        if user_id in self.reminder_tasks:
            self.reminder_tasks[user_id].cancel()
        
        self.reminder_tasks[user_id] = asyncio.create_task(
            self._reminder_loop(user_id, schedule)
        )

    async def stop_reminder(self, user_id: str):
        """停止提醒任务"""
        if user_id in self.reminder_tasks:
            self.reminder_tasks[user_id].cancel()
            del self.reminder_tasks[user_id]

    async def _reminder_loop(self, user_id: str, schedule: List[Dict]):
        """提醒循环"""
        while True:
            try:
                # 获取当前时间
                now = datetime.now()
                
                # 获取今日课程
                today_schedule = self._get_today_courses(schedule)
                
                # 检查是否需要提醒
                for course in today_schedule:
                    course_time = self._parse_course_time(course['time'])
                    if course_time:
                        reminder_time = course_time - timedelta(minutes=self.reminder_time)
                        if now >= reminder_time and now < course_time:
                            # 发送提醒
                            if self.callback:
                                await self.callback(user_id, [course])
                
                # 等待一分钟
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"提醒循环出错: {str(e)}")
                await asyncio.sleep(60)

    def _get_today_courses(self, schedule: List[Dict]) -> List[Dict]:
        """获取今日课程"""
        # 获取当前星期
        today = datetime.now().strftime('%A')
        current_day = self.week_map.get(today, '未知')
        
        # 获取当前周次
        current_week = self._get_current_week()
        
        # 筛选今日课程
        today_schedule = [
            course for course in schedule
            if course['day'] == current_day
            and current_week >= course['start_week']
            and current_week <= course['end_week']
        ]
        
        # 按节次排序
        today_schedule.sort(key=lambda x: x['period'])
        
        return today_schedule

    def _parse_course_time(self, time_str: str) -> Optional[datetime]:
        """解析课程时间"""
        try:
            # 解析时间字符串（格式：HH:MM-HH:MM）
            start_time = time_str.split('-')[0]
            hour, minute = map(int, start_time.split(':'))
            
            # 获取当前日期
            now = datetime.now()
            
            # 创建课程时间
            course_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            return course_time
        except Exception as e:
            self.logger.error(f"解析课程时间失败: {str(e)}")
            return None

    def _get_current_week(self) -> int:
        """获取当前周次"""
        # 假设第一周从9月1日开始
        start_date = datetime(2024, 9, 1)
        current_date = datetime.now()
        
        # 计算周差
        week_diff = (current_date - start_date).days // 7
        return week_diff + 1 

    def get_today_weekday(self) -> str:
        """获取今天的星期"""
        return self.week_map.get(datetime.now().strftime('%A'), '未知')

    def get_class_time_from_str(self, time_str: str) -> Optional[tuple]:
        """从时间字符串解析上课时间"""
        try:
            # 解析时间字符串（格式：HH:MM-HH:MM）
            start_time = time_str.split('-')[0]
            hour, minute = map(int, start_time.split(':'))
            return (hour, minute)
        except:
            return None

    def load_schedule(self, user_id: str) -> List[Dict[str, Any]]:
        """加载用户的课程表"""
        try:
            file_path = os.path.join(self.data_dir, f"{user_id}.json")
            if not os.path.exists(file_path):
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('courses', [])
        except Exception as e:
            print(f"加载课程表失败: {str(e)}")
            return []

    def get_today_courses(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户今天的课程"""
        today = self.get_today_weekday()
        courses = self.load_schedule(user_id)
        
        # 筛选今天的课程
        today_courses = [
            course for course in courses
            if course['day'] == today
        ]
        
        # 按时间排序
        today_courses.sort(key=lambda x: self.get_class_time_from_str(x['time']))
        
        return today_courses

    def get_upcoming_courses(self, user_id: str) -> List[Dict[str, Any]]:
        """获取即将开始的课程"""
        now = datetime.now()
        today_courses = self.get_today_courses(user_id)
        upcoming_courses = []
        
        for course in today_courses:
            class_time = self.get_class_time_from_str(course['time'])
            if not class_time:
                continue
            
            # 计算课程开始时间
            class_dt = now.replace(
                hour=class_time[0],
                minute=class_time[1],
                second=0,
                microsecond=0
            )
            
            # 计算时间差（分钟）
            time_diff = (class_dt - now).total_seconds() / 60
            
            # 如果课程即将开始（在提醒时间范围内）
            if 0 < time_diff <= self.reminder_time:
                upcoming_courses.append(course)
        
        return upcoming_courses

    async def check_and_remind(self, callback) -> None:
        """检查并发送提醒"""
        try:
            # 遍历所有用户
            for file_name in os.listdir(self.data_dir):
                if not file_name.endswith('.json'):
                    continue
                
                user_id = file_name[:-5]  # 移除.json后缀
                
                # 获取即将开始的课程
                upcoming_courses = self.get_upcoming_courses(user_id)
                
                # 发送提醒
                for course in upcoming_courses:
                    reminder_msg = (
                        f"上课提醒：\n"
                        f"课程：{course['course_name']}\n"
                        f"时间：{course['time']}\n"
                        f"地点：{course['classroom']}\n"
                        f"教师：{course['teacher']}"
                    )
                    await callback(user_id, reminder_msg)
        except Exception as e:
            print(f"检查课程提醒失败: {str(e)}")

    async def start_reminder_loop(self, callback, interval: int = 60) -> None:
        """
        启动提醒循环
        
        Args:
            callback: 提醒回调函数，接收用户ID和提醒消息
            interval: 检查间隔（秒）
        """
        while True:
            await self.check_and_remind(callback)
            await asyncio.sleep(interval) 