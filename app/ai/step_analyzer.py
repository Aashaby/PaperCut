import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import math
import logging
import traceback
import svgwrite
from typing import List, Dict, Tuple, Any

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StepAnalyzer:
    def __init__(self):
        """初始化 StepAnalyzer"""
        # 图像处理参数
        self.target_size = 800  # 图像处理的目标尺寸
        
        # 轮廓处理参数
        self.min_contour_area = 7  # 最小轮廓面积
        self.min_contour_length = 50 # 新增参数：最小轮廓长度
        self.epsilon_factor = 0.005  # 多边形逼近的精度因子
        
        # 边缘检测参数
        self.low_threshold_ratio = 0.15  # Canny 低阈值比例
        self.high_threshold_ratio = 0.25  # Canny 高阈值比例
        
        # SVG 参数
        self.svg_width = 800  # SVG 宽度
        self.svg_height = 800  # SVG 高度
        self.svg_padding = 20  # SVG 边距
        self.svg_stroke_width = 2  # SVG 线宽
        
        # 可视化参数
        self.viz_stroke_width = 3  # 可视化线宽
        self.arrow_length = 25  # 箭头长度
        self.min_segment_length = 10  # 最小线段长度
        self.font = ImageFont.truetype("arial.ttf", 12)

    def _get_direction_description(self, angle: float) -> str:
        """获取人类可读的方向描述"""
        angle = angle % 360
        
        if 337.5 <= angle or angle < 22.5:
            return "向右"
        elif 22.5 <= angle < 67.5:
            return "向右下"
        elif 67.5 <= angle < 112.5:
            return "向下"
        elif 112.5 <= angle < 157.5:
            return "向左下"
        elif 157.5 <= angle < 202.5:
            return "向左"
        elif 202.5 <= angle < 247.5:
            return "向左上"
        elif 247.5 <= angle < 292.5:
            return "向上"
        else:  # 292.5 到 337.5
            return "向右上"

    def _get_direction_angle(self, direction: str) -> float:
        """将方向描述转换为角度"""
        directions = {
            "向右": 0,
            "向右下": 45,
            "向下": 90,
            "向左下": 135,
            "向左": 180,
            "向左上": 225,
            "向上": 270,
            "向右上": 315
        }
        return directions.get(direction, 0)

    def _convert_to_python_types(self, data: Any) -> Any:
        """递归地将 numpy 类型转换为原生 Python 类型以便 JSON 序列化。"""
        if isinstance(data, dict):
            return {key: self._convert_to_python_types(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._convert_to_python_types(element) for element in data]
        elif isinstance(data, tuple):
            return tuple(self._convert_to_python_types(element) for element in data)
        elif isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.floating):
            return float(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        return data

    def analyze(self, image_data: str) -> Dict[str, Any]:
        """分析图像并生成绘图指令"""
        try:
            logger.info("开始图像分析")
            
            if not image_data:
                return {}
            
            try:
                # 处理图像数据
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
                
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                image.thumbnail((self.target_size, self.target_size))
                image_np = np.array(image)
                logger.info(f"处理后的图像尺寸: {image_np.shape}")
                
            except Exception as e:
                logger.error(f"图像处理失败: {str(e)}")
                return {}
            
            # 转为灰度并高斯模糊
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # 应用 Canny 边缘检测
            v = np.median(blurred)
            low_threshold = int(max(0, (1.0 - self.low_threshold_ratio) * v))
            high_threshold = int(min(255, (1.0 + self.high_threshold_ratio) * v))
            logger.info(f"使用 Canny 阈值: Low={low_threshold}, High={high_threshold}")
            edges = cv2.Canny(blurred, low_threshold, high_threshold)
            
            # 查找轮廓
            contours, hierarchy = cv2.findContours(
                edges,
                cv2.RETR_TREE,
                cv2.CHAIN_APPROX_NONE  # 更详细的轮廓
            )
            
            if not contours:
                logger.warning("未找到轮廓")
                return {}
            
            # 创建 SVG 绘图对象
            svg_drawing = svgwrite.Drawing(
                size=(self.svg_width, self.svg_height),
                viewBox=f"0 0 {self.svg_width} {self.svg_height}"
            )
            svg_drawing.add(svg_drawing.rect(
                insert=(0, 0),
                size=('100%', '100%'),
                fill='white'
            ))
            
            # 处理轮廓
            all_steps = []
            contour_index = 0
            
            # 计算缩放因子
            all_points = np.vstack(contours)
            x, y, w, h = cv2.boundingRect(all_points)
            scale_x = (self.svg_width - 2 * self.svg_padding) / w
            scale_y = (self.svg_height - 2 * self.svg_padding) / h
            scale = min(scale_x, scale_y)
            
            # 计算偏移量以居中图案
            offset_x = (self.svg_width - w * scale) / 2
            offset_y = (self.svg_height - h * scale) / 2
            
            # 使用层级信息处理轮廓，实现由内到外的顺序
            processed_contours = set()
            # 创建元组列表 (contour_index, contour, hierarchy_info)
            contour_info = [(i, contours[i], hierarchy[0][i]) for i in range(len(contours))]

            # 排序轮廓：先洞，后父轮廓，再按面积（小的在前）
            # 这样可以实现由内到外的绘制顺序
            contour_info.sort(key=lambda item: (item[2][3] == -1, item[2][3], cv2.contourArea(item[1])))

            for i, contour, hier in contour_info:
                # 首先将所有轮廓绘制到 SVG
                path_data = "M "
                for point in contour:
                    x = point[0][0] * scale + offset_x
                    y = point[0][1] * scale + offset_y
                    path_data += f"{('L' if path_data != 'M ' else '')}{x:.1f},{y:.1f} "
                path_data += "Z"
                
                is_hole = hier[3] != -1
                stroke_color = 'black' if not is_hole else 'gray'
                svg_drawing.add(svg_drawing.path(d=path_data, stroke=stroke_color, fill='none', stroke_width=self.svg_stroke_width))

            # 现在，基于排序后的轮廓生成步骤
            for i, contour, hier in contour_info:
                area = cv2.contourArea(contour)
                if area < self.min_contour_area:
                    continue

                contour_index += 1
                all_steps.append({
                    'step': len(all_steps) + 1,
                    'description': f"开始处理第 {contour_index} 部分",
                    'type': 'start',
                    'contour_index': contour_index
                })

                # --- 新的笔画分段逻辑 ---
                # 简化轮廓以找到关键角点/顶点
                perimeter = cv2.arcLength(contour, True)
                corners = cv2.approxPolyDP(contour, self.epsilon_factor * perimeter, True)

                if len(corners) < 2:
                    continue

                # 在原始轮廓中查找角点索引
                corner_indices = []
                for corner in corners:
                    # 查找该角点在原始轮廓中的索引
                    distances = np.sqrt(np.sum((contour - corner) ** 2, axis=2))
                    index = np.argmin(distances)
                    if not corner_indices or corner_indices[-1] != index:
                         corner_indices.append(index)
                corner_indices.sort()

                # 在角点之间生成笔画
                for j in range(len(corner_indices)):
                    start_corner_idx = corner_indices[j]
                    end_corner_idx = corner_indices[(j + 1) % len(corner_indices)]
                    
                    # 提取该笔画的点
                    if start_corner_idx < end_corner_idx:
                        stroke_points = contour[start_corner_idx:end_corner_idx + 1]
                    else: # 封闭笔画时需要首尾拼接
                        stroke_points = np.vstack((contour[start_corner_idx:], contour[:end_corner_idx+1]))

                    if len(stroke_points) < 2:
                        continue

                    # 分析该笔画以获得更好的描述
                    start_point = tuple(stroke_points[0][0])
                    end_point = tuple(stroke_points[-1][0])

                    dx = end_point[0] - start_point[0]
                    dy = end_point[1] - start_point[1]
                    
                    # 路径长度与直线距离，用于判断曲线/直线
                    path_length = cv2.arcLength(stroke_points, False)
                    direct_dist = math.sqrt(dx*dx + dy*dy)

                    shape_type = "直线" if path_length < direct_dist * 1.1 else "曲线"
                    length_desc = "长" if path_length > 80 else ("短" if path_length < 30 else "")
                    direction = self._get_direction_description(math.degrees(math.atan2(dy, dx)))

                    description = f"沿{direction}切一条{length_desc}{shape_type}"

                    all_steps.append({
                        'step': len(all_steps) + 1,
                        'description': description,
                        'start_point': start_point,
                        'end_point': end_point,
                        'type': 'draw',
                        'length': path_length,
                        'direction': direction,
                        'contour_index': contour_index,
                        'path_pixels': [tuple(p[0]) for p in stroke_points] # 用于 UI 高亮
                    })

                all_steps.append({
                    'step': len(all_steps) + 1,
                    'description': f"完成第 {contour_index} 部分",
                    'type': 'end',
                    'contour_index': contour_index
                })
            
            if not all_steps:
                logger.warning("未生成有效绘图步骤")
                return {}
            
            # 生成可视化图像
            vis_image = image_np.copy()
            pil_image = Image.fromarray(vis_image)
            draw = ImageDraw.Draw(pil_image)
            
            contour_colors = [
                (255, 0, 0),    # 红色
                (0, 100, 0),    # 绿色
                (0, 0, 255),    # 蓝色
                (128, 0, 128),  # 紫色
                (255, 165, 0),  # 橙色
            ]
            
            last_positions = {}
            
            for step in all_steps:
                contour_idx = step.get('contour_index', 0)
                color_idx = (contour_idx - 1) % len(contour_colors)
                color = contour_colors[color_idx]
                
                if step['type'] == 'start':
                    # 查找该轮廓的第一个绘制步骤以获取起点
                    first_draw_step = next((s for s in all_steps if s.get('contour_index') == contour_idx and s.get('type') == 'draw'), None)
                    if first_draw_step:
                        point = first_draw_step['start_point']
                        draw.ellipse([point[0]-6, point[1]-6, point[0]+6, point[1]+6], 
                                   fill=(0, 255, 0), outline=(0, 150, 0), width=2)
                        last_positions[contour_idx] = point
                
                elif step['type'] == 'draw':
                    start = step['start_point']
                    end = step['end_point']
                    
                    # 使用 path_pixels 以更精确地在可视化图像上绘制线条
                    if 'path_pixels' in step and len(step['path_pixels']) > 1:
                        draw.line(step['path_pixels'], fill=color, width=self.viz_stroke_width)
                    else:
                        draw.line([start, end], fill=color, width=self.viz_stroke_width)

                    # 按用户要求，去除步骤注释，保持极简。
                    
                    last_positions[contour_idx] = end
                
                elif step['type'] == 'end':
                    # 查找该轮廓的最后一个绘制步骤以获取终点
                    last_draw_step = next((s for s in reversed(all_steps) if s.get('contour_index') == contour_idx and s.get('type') == 'draw'), None)
                    if last_draw_step:
                        point = last_draw_step['end_point']
                        draw.ellipse([point[0]-6, point[1]-6, point[0]+6, point[1]+6], 
                                   fill=(255, 50, 50), outline=(150, 0, 0), width=2)
                        last_positions[contour_idx] = point
            
            buffered = io.BytesIO()
            pil_image.save(buffered, format="PNG")
            visualization = base64.b64encode(buffered.getvalue()).decode()
            
            # 完成 SVG
            svg_data = svg_drawing.tostring()
            
            logger.info(f"生成了 {len(all_steps)} 个绘图步骤")
            
            result = {
                'steps': all_steps,
                'svg_data': svg_data,
                'visualization': visualization
            }
            
            return self._convert_to_python_types(result)
            
        except Exception as e:
            logger.error(f"分析出错: {str(e)}")
            logger.error(traceback.format_exc())
            return {}