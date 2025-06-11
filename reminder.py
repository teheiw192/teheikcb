import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Awaitable

class CourseReminder:
    def __init__(self, reminder_time: int = 10):
        self.reminder_time = reminder_time
        self.logger = logging.getLogger("CourseReminder")
        self.reminder_tasks: Dict[str, asyncio.Task] = {}
        self.callback: Optional[Callable[[str, List[Dict]], Awaitable[None]]] = None

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
        from datetime import datetime
        import locale
        
        # 设置中文locale
        locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
        
        # 获取当前星期
        today = datetime.now().strftime('%A')
        week_map = {
            'Monday': '星期一',
            'Tuesday': '星期二',
            'Wednesday': '星期三',
            'Thursday': '星期四',
            'Friday': '星期五',
            'Saturday': '星期六',
            'Sunday': '星期日'
        }
        current_day = week_map.get(today, '未知')
        
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