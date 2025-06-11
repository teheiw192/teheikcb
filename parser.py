import os
import re
import json
import pandas as pd
from docx import Document
from PIL import Image
import pytesseract
from typing import List, Dict, Optional, Tuple
import logging

class ScheduleParser:
    def __init__(self, data_dir: str, ocr_config: Dict):
        self.data_dir = data_dir
        self.ocr_config = ocr_config
        self.logger = logging.getLogger("ScheduleParser")
        
        # 创建数据目录
        os.makedirs(data_dir, exist_ok=True)
        
        # 课程时间映射
        self.time_slots = {
            1: "08:00-08:45",
            2: "08:55-09:40",
            3: "10:00-10:45",
            4: "10:55-11:40",
            5: "14:00-14:45",
            6: "14:55-15:40",
            7: "16:00-16:45",
            8: "16:55-17:40",
            9: "19:00-19:45",
            10: "19:55-20:40"
        }

    def parse_docx(self, file_path: str) -> List[Dict]:
        """解析Word文档格式的课程表"""
        try:
            doc = Document(file_path)
            schedule = []
            
            # 提取表格数据
            for table in doc.tables:
                for row in table.rows[1:]:  # 跳过表头
                    for cell in row.cells:
                        if cell.text.strip():
                            course_info = self._parse_course_text(cell.text)
                            if course_info:
                                schedule.append(course_info)
            
            return schedule
        except Exception as e:
            self.logger.error(f"解析Word文档失败: {str(e)}")
            return []

    def parse_image(self, image_path: str) -> List[Dict]:
        """解析图片格式的课程表"""
        try:
            # 使用OCR识别图片中的文字
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='chi_sim')
            
            # 解析识别出的文本
            schedule = []
            lines = text.split('\n')
            current_course = {}
            
            for line in lines:
                if not line.strip():
                    continue
                    
                # 尝试提取课程信息
                course_info = self._parse_course_text(line)
                if course_info:
                    schedule.append(course_info)
            
            return schedule
        except Exception as e:
            self.logger.error(f"解析图片失败: {str(e)}")
            return []

    def parse_excel(self, file_path: str) -> List[Dict]:
        """解析Excel格式的课程表"""
        try:
            df = pd.read_excel(file_path)
            schedule = []
            
            # 遍历数据框的每一行
            for _, row in df.iterrows():
                for col in df.columns:
                    if pd.notna(row[col]):
                        course_info = self._parse_course_text(str(row[col]))
                        if course_info:
                            schedule.append(course_info)
            
            return schedule
        except Exception as e:
            self.logger.error(f"解析Excel文件失败: {str(e)}")
            return []

    def _parse_course_text(self, text: str) -> Optional[Dict]:
        """解析课程文本信息"""
        try:
            # 课程名称
            course_name = re.search(r'[\u4e00-\u9fa5]{2,}', text)
            if not course_name:
                return None
            course_name = course_name.group()
            
            # 教师名称
            teacher = re.search(r'[\u4e00-\u9fa5]{2,}(?:老师|教授)', text)
            teacher = teacher.group() if teacher else "未知"
            
            # 教室
            classroom = re.search(r'[A-Z]\d{3}', text)
            classroom = classroom.group() if classroom else "未知"
            
            # 周次
            weeks = re.search(r'第(\d+)-(\d+)周', text)
            if weeks:
                start_week = int(weeks.group(1))
                end_week = int(weeks.group(2))
            else:
                start_week = 1
                end_week = 16
            
            # 星期和节次
            day = re.search(r'星期[一二三四五六日]', text)
            day = day.group() if day else "未知"
            
            period = re.search(r'第(\d+)节', text)
            period = int(period.group(1)) if period else 1
            
            return {
                "course_name": course_name,
                "teacher": teacher,
                "classroom": classroom,
                "start_week": start_week,
                "end_week": end_week,
                "day": day,
                "period": period,
                "time": self.time_slots.get(period, "未知")
            }
        except Exception as e:
            self.logger.error(f"解析课程文本失败: {str(e)}")
            return None

    def save_schedule(self, user_id: str, schedule: List[Dict]) -> bool:
        """保存课程表"""
        try:
            file_path = os.path.join(self.data_dir, f"{user_id}_schedule.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(schedule, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存课程表失败: {str(e)}")
            return False

    def load_schedule(self, user_id: str) -> List[Dict]:
        """加载课程表"""
        try:
            file_path = os.path.join(self.data_dir, f"{user_id}_schedule.json")
            if not os.path.exists(file_path):
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载课程表失败: {str(e)}")
            return []

    def get_today_schedule(self, user_id: str) -> List[Dict]:
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
        
        # 加载课程表
        schedule = self.load_schedule(user_id)
        
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

    def _get_current_week(self) -> int:
        """获取当前周次"""
        from datetime import datetime
        
        # 假设第一周从9月1日开始
        start_date = datetime(2024, 9, 1)
        current_date = datetime.now()
        
        # 计算周差
        week_diff = (current_date - start_date).days // 7
        return week_diff + 1 