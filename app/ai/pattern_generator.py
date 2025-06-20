import requests
import os
from PIL import Image
import io
from functools import lru_cache
import logging
import base64
import time
import traceback

logger = logging.getLogger(__name__)

class PatternGenerator:
    def __init__(self):
        self.api_key = os.getenv("STABLE_DIFFUSION_API_KEY")
        if not self.api_key:
            logging.warning("未在.env文件中找到 STABLE_DIFFUSION_API_KEY，部分功能将不可用。")
        self.api_url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
        self.max_retries = 1  # 增加重试次数
        self.retry_delay = 30  # 秒
        self.timeout = 120  # 增加超时时间

    def _process_image(self, image_data: str) -> str:
        """处理生成的图片，确保适合剪纸绘制
        
        参数：
            image_data: Base64 编码的图片数据
            
        返回：
            str: 处理后的 Base64 编码图片数据
        """
        try:
            # 解码 base64 图片
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # 如有需要，转换为 RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 转为灰度图
            image = image.convert('L')
            
            # 增强对比度
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)  # 增加对比度
            
            # 转回 RGB
            image = image.convert('RGB')
            
            # 保存为字节流
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
            
        except Exception as e:
            logger.error(f"处理图片出错: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise

    @lru_cache(maxsize=100)
    def generate(self, prompt: str) -> str:
        """根据文本提示生成剪纸图案
        
        参数：
            prompt: 所需图案的文本描述
            
        返回：
            str: Base64 编码的图片数据
            
        异常：
            Exception: 如果生成失败
        """
        if not prompt or not isinstance(prompt, str):
            raise ValueError("无效的提示词: 必须为非空字符串")
            
        for attempt in range(self.max_retries):
            try:
                logger.info(f"为提示词生成图案: {prompt} (第 {attempt + 1}/{self.max_retries} 次尝试)")
                
                # 构建增强提示词（保留英文内容）
                enhanced_prompt = f"""
                A traditional Chinese paper cutting pattern of {prompt},
                clean and precise lines,
                very very easy,
                suitable for paper cutting,
                black and white,
                high contrast,
                vector style,
                symmetrical design,
                traditional Chinese art style,
                detailed edges,
                no shading,
                no gradients,
                single layer design,
                suitable for cutting with scissors,
                clear cutting lines,
                traditional paper cutting technique,
                cultural elements,
                decorative pattern
                """

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }

                body = {
                    "text_prompts": [
                        {
                            "text": enhanced_prompt,
                            "weight": 1
                        },
                        {
                            "text": "photorealistic, 3d, shading, gradient, multiple layers, complex background, blurry, low contrast, modern style, digital art, painting, sketch, watercolor, oil painting, realistic, detailed shading, multiple colors, complex textures",
                            "weight": -1
                        }
                    ],
                    "cfg_scale": 7,
                    "height": 1024,
                    "width": 1024,
                    "samples": 1,
                    "steps": 30,
                    "style_preset": "line-art"
                }

                logger.debug(f"发送请求到 Stability AI API")
                logger.debug(f"请求 URL: {self.api_url}")
                
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout
                )
                
                logger.debug(f"响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if "artifacts" in data and len(data["artifacts"]) > 0:
                        image_data = data["artifacts"][0]["base64"]
                        logger.info("成功生成图案")
                        
                        # 处理图片
                        processed_image = self._process_image(image_data)
                        logger.info("成功处理图案图片")
                        return processed_image
                    else:
                        error_msg = "响应中无图片数据"
                        logger.error(error_msg)
                        logger.debug(f"响应数据: {data}")
                        raise Exception(error_msg)
                elif response.status_code == 401:
                    error_msg = "API 认证失败，请检查 API 密钥。"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                elif response.status_code == 429:
                    error_msg = "API 速率限制超出，请稍后再试。"
                    logger.error(error_msg)
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    raise Exception(error_msg)
                else:
                    error_msg = f"API 请求失败，状态码 {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
            except requests.exceptions.Timeout:
                error_msg = "API 请求超时"
                logger.error(error_msg)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise Exception(error_msg)
            except requests.exceptions.RequestException as e:
                error_msg = f"API 请求失败: {str(e)}"
                logger.error(error_msg)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise Exception(error_msg)
            except Exception as e:
                logger.error(f"图案生成出错: {str(e)}")
                logger.error(f"详细错误: {traceback.format_exc()}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise
                
        raise Exception("所有重试后仍未成功生成图案") 