"""
课程表解析模块
支持解析Word、Excel和图片格式的课程表
"""
import os
import json
import re
from typing import List, Dict, Any, Optional
import docx
import pandas as pd
from PIL import Image
import pytesseract
from datetime import datetime
import locale

class ScheduleParser:
    def __init__(self):
        # 设置中文环境
        locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
        
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
        
        # 时间映射
        self.time_map = {
            '第1-2节': '08:00-09:40',
            '第3-4节': '10:00-11:40',
            '第5-6节': '14:00-15:40',
            '第7-8节': '16:00-17:40',
            '第9-10节': '19:00-20:40'
        }

    def parse_word(self, file_path: str) -> List[Dict[str, Any]]:
        """解析Word格式的课程表"""
        try:
            doc = docx.Document(file_path)
            courses = []
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                    
                # 尝试解析课程信息
                course_info = self._parse_course_text(text)
                if course_info:
                    courses.append(course_info)
            
            return courses
        except Exception as e:
            print(f"解析Word文件失败: {str(e)}")
            return []

    def parse_xlsx(self, file_path: str) -> List[Dict[str, Any]]:
        """解析Excel格式的课程表"""
        try:
            df = pd.read_excel(file_path)
            courses = []
            
            # 遍历每一行
            for _, row in df.iterrows():
                # 将行数据转换为字典
                row_dict = row.to_dict()
                
                # 尝试解析课程信息
                course_info = self._parse_course_dict(row_dict)
                if course_info:
                    courses.append(course_info)
            
            return courses
        except Exception as e:
            print(f"解析Excel文件失败: {str(e)}")
            return []

    def parse_image(self, file_path: str) -> List[Dict[str, Any]]:
        """解析图片格式的课程表"""
        try:
            # 打开图片
            image = Image.open(file_path)
            
            # 使用OCR识别文字
            text = pytesseract.image_to_string(image, lang='chi_sim')
            
            # 按行分割
            lines = text.split('\n')
            courses = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 尝试解析课程信息
                course_info = self._parse_course_text(line)
                if course_info:
                    courses.append(course_info)
            
            return courses
        except Exception as e:
            print(f"解析图片文件失败: {str(e)}")
            return []

    def parse_text_schedule(self, text: str) -> List[Dict[str, Any]]:
        """解析文本格式的课程表"""
        try:
            # 按行分割
            lines = text.split('\n')
            courses = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 尝试解析课程信息
                course_info = self._parse_course_text(line)
                if course_info:
                    courses.append(course_info)
            
            return courses
        except Exception as e:
            print(f"解析文本失败: {str(e)}")
            return []

    def _parse_course_text(self, text: str) -> Optional[Dict[str, Any]]:
        """解析课程文本"""
        try:
            # 使用正则表达式匹配课程信息
            pattern = r'(.+?)\s+([一二三四五六日]|星期[一二三四五六日])\s+([\d:-]+)\s+(.+?)\s+(.+)'
            match = re.match(pattern, text)
            
            if match:
                course_name, day, time, classroom, teacher = match.groups()
                
                # 标准化星期格式
                day = self._standardize_day(day)
                
                # 标准化时间格式
                time = self._standardize_time(time)
                
                return {
                    'course_name': course_name.strip(),
                    'day': day,
                    'time': time,
                    'classroom': classroom.strip(),
                    'teacher': teacher.strip()
                }
            
            return None
        except Exception as e:
            print(f"解析课程文本失败: {str(e)}")
            return None

    def _parse_course_dict(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析课程字典"""
        try:
            # 尝试从字典中提取课程信息
            course_name = data.get('课程名称', data.get('课程', ''))
            day = data.get('星期', data.get('上课时间', ''))
            time = data.get('节次', data.get('时间', ''))
            classroom = data.get('教室', data.get('地点', ''))
            teacher = data.get('教师', data.get('老师', ''))
            
            if not all([course_name, day, time, classroom, teacher]):
                return None
            
            # 标准化星期格式
            day = self._standardize_day(day)
            
            # 标准化时间格式
            time = self._standardize_time(time)
            
            return {
                'course_name': str(course_name).strip(),
                'day': day,
                'time': time,
                'classroom': str(classroom).strip(),
                'teacher': str(teacher).strip()
            }
        except Exception as e:
            print(f"解析课程字典失败: {str(e)}")
            return None

    def _standardize_day(self, day: str) -> str:
        """标准化星期格式"""
        # 将"一二三四五六日"转换为"星期X"
        if len(day) == 1 and day in '一二三四五六日':
            return f'星期{day}'
        
        # 将"周X"转换为"星期X"
        if day.startswith('周'):
            return f'星期{day[1:]}'
        
        return day

    def _standardize_time(self, time: str) -> str:
        """标准化时间格式"""
        # 如果是节次格式，转换为具体时间
        if '第' in time and '节' in time:
            for key, value in self.time_map.items():
                if key in time:
                    return value
        
        return time

def parse_word(file_path: str) -> List[Dict[str, Any]]:
    """解析Word格式的课程表"""
    parser = ScheduleParser()
    return parser.parse_word(file_path)

def parse_xlsx(file_path: str) -> List[Dict[str, Any]]:
    """解析Excel格式的课程表"""
    parser = ScheduleParser()
    return parser.parse_xlsx(file_path)

def parse_image(file_path: str) -> List[Dict[str, Any]]:
    """解析图片格式的课程表"""
    parser = ScheduleParser()
    return parser.parse_image(file_path)

def parse_text_schedule(text: str) -> List[Dict[str, Any]]:
    """解析文本格式的课程表"""
    parser = ScheduleParser()
    return parser.parse_text_schedule(text) 