import os
import json
import random
from typing import Optional, List, Dict
from PIL import Image
import io

class Gallery:
    def __init__(self, name: str, path: str, creator_id: str, creator_name: str, 
                 capacity: int = 200, compress: bool = True, duplicate: bool = True, fuzzy: bool = False):
        self.name = name
        self.path = path
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.capacity = capacity
        self.compress = compress
        self.duplicate = duplicate
        self.fuzzy = fuzzy
        self.keywords = []
        os.makedirs(path, exist_ok=True)

    def add_image(self, image: bytes, label: str = "") -> str:
        """添加图片到图库"""
        if len(os.listdir(self.path)) >= self.capacity:
            raise Exception(f"图库【{self.name}】已达到容量上限")
        
        # 检查重复
        if self.duplicate:
            for filename in os.listdir(self.path):
                if self._is_same_image(image, os.path.join(self.path, filename)):
                    return f"图片已存在于图库【{self.name}】中"

        # 压缩图片
        if self.compress:
            image = self._compress_image(image)

        # 保存图片
        filename = f"{label}_{len(os.listdir(self.path)) + 1}.png"
        filepath = os.path.join(self.path, filename)
        with open(filepath, "wb") as f:
            f.write(image)
        return f"图片已添加到图库【{self.name}】中"

    def delete_image(self, index: Optional[int] = None) -> str:
        """删除图库中的图片"""
        if index is None:
            # 删除整个图库
            for filename in os.listdir(self.path):
                os.remove(os.path.join(self.path, filename))
            return f"图库【{self.name}】已清空"
        
        # 删除指定图片
        files = sorted(os.listdir(self.path))
        if 1 <= index <= len(files):
            os.remove(os.path.join(self.path, files[index - 1]))
            return f"已删除图库【{self.name}】中的第{index}张图片"
        return f"图库【{self.name}】中没有第{index}张图片"

    def get_image(self, index: Optional[int] = None) -> Optional[str]:
        """获取图库中的图片"""
        files = sorted(os.listdir(self.path))
        if not files:
            return None
        
        if index is None:
            # 随机返回一张图片
            return os.path.join(self.path, random.choice(files))
        
        if 1 <= index <= len(files):
            return os.path.join(self.path, files[index - 1])
        return None

    def get_info(self) -> Dict:
        """获取图库信息"""
        return {
            "name": self.name,
            "creator_id": self.creator_id,
            "creator_name": self.creator_name,
            "capacity": self.capacity,
            "compress": self.compress,
            "duplicate": self.duplicate,
            "fuzzy": self.fuzzy,
            "keywords": self.keywords,
            "image_count": len(os.listdir(self.path))
        }

    def _compress_image(self, image_data: bytes) -> bytes:
        """压缩图片"""
        img = Image.open(io.BytesIO(image_data))
        if max(img.size) > 512:
            ratio = 512 / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True)
        return output.getvalue()

    def _is_same_image(self, image1: bytes, image2_path: str) -> bool:
        """检查两张图片是否相同"""
        try:
            img1 = Image.open(io.BytesIO(image1))
            img2 = Image.open(image2_path)
            return img1.size == img2.size and img1.tobytes() == img2.tobytes()
        except:
            return False

class GalleryManager:
    def __init__(self, base_dir: str, info_file: str, default_gallery_info: Dict):
        self.base_dir = base_dir
        self.info_file = info_file
        self.default_gallery_info = default_gallery_info
        self.galleries: Dict[str, Gallery] = {}
        self.exact_keywords: List[str] = []
        self.fuzzy_keywords: List[str] = []
        os.makedirs(base_dir, exist_ok=True)
        self._load_info()

    def _load_info(self):
        """加载图库信息"""
        if os.path.exists(self.info_file):
            with open(self.info_file, "r", encoding="utf-8") as f:
                info = json.load(f)
                self.exact_keywords = info.get("exact_keywords", [])
                self.fuzzy_keywords = info.get("fuzzy_keywords", [])
                for gallery_info in info.get("galleries", []):
                    self.galleries[gallery_info["name"]] = Gallery(**gallery_info)

    def _save_info(self):
        """保存图库信息"""
        info = {
            "exact_keywords": self.exact_keywords,
            "fuzzy_keywords": self.fuzzy_keywords,
            "galleries": [gallery.get_info() for gallery in self.galleries.values()]
        }
        with open(self.info_file, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

    def get_gallery(self, name: str) -> Optional[Gallery]:
        """获取图库"""
        return self.galleries.get(name)

    def create_gallery(self, name: str, creator_id: str, creator_name: str) -> Gallery:
        """创建图库"""
        if name in self.galleries:
            raise Exception(f"图库【{name}】已存在")
        
        gallery_info = self.default_gallery_info.copy()
        gallery_info.update({
            "name": name,
            "path": os.path.join(self.base_dir, name),
            "creator_id": creator_id,
            "creator_name": creator_name
        })
        
        gallery = Gallery(**gallery_info)
        self.galleries[name] = gallery
        self._save_info()
        return gallery

    def delete_gallery(self, name: str) -> str:
        """删除图库"""
        if name not in self.galleries:
            return f"图库【{name}】不存在"
        
        gallery = self.galleries[name]
        for filename in os.listdir(gallery.path):
            os.remove(os.path.join(gallery.path, filename))
        os.rmdir(gallery.path)
        del self.galleries[name]
        self._save_info()
        return f"图库【{name}】已删除"

    def get_gallery_by_keyword(self, keyword: str) -> List[Gallery]:
        """通过关键词获取图库"""
        return [g for g in self.galleries.values() if keyword in g.keywords]

    def get_gallery_by_attribute(self, **kwargs) -> List[Gallery]:
        """通过属性获取图库"""
        return [g for g in self.galleries.values() if all(getattr(g, k) == v for k, v in kwargs.items())] 