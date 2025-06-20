from flask import Flask, render_template, request, jsonify
from ai.pattern_generator import PatternGenerator
from ai.step_analyzer import StepAnalyzer
from hardware.arduino_controller import ArduinoController
import os
from dotenv import load_dotenv
import logging
import base64
import traceback
from typing import Dict, Any, List, Optional, Union
import json
import io
from PIL import Image

# 加载环境变量配置
load_dotenv()

# 配置日志系统
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 创建Flask应用实例
app = Flask(__name__, 
    static_folder='static',
    template_folder='templates'
)

# 初始化核心组件
try:
    pattern_generator = PatternGenerator()
    step_analyzer = StepAnalyzer()
    arduino_controller = ArduinoController()
    logger.info("所有核心组件初始化成功")
except Exception as e:
    logger.error(f"组件初始化失败: {str(e)}")
    logger.error(f"详细错误信息: {traceback.format_exc()}")
    raise

@app.route('/')
def index():
    """渲染主页
    
    Returns:
        str: 渲染后的HTML页面
    """
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"渲染主页时发生错误: {str(e)}")
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return "服务器错误，请稍后重试", 500

@app.route('/generate_pattern', methods=['POST'])
def generate_pattern():
    """生成剪纸图案的API端点
    
    Returns:
        tuple: (JSON响应, HTTP状态码)
    """
    try:
        # 获取并验证用户输入
        if not request.is_json:
            logger.warning("请求格式不是JSON")
            return jsonify({'error': '请求格式必须是JSON'}), 400
            
        prompt = request.json.get('prompt')
        if not prompt:
            logger.warning("用户未提供提示词")
            return jsonify({'error': '请提供生成图案的关键词'}), 400
            
        if not isinstance(prompt, str):
            logger.warning(f"提示词类型无效: {type(prompt)}")
            return jsonify({'error': '提示词必须是字符串'}), 400
            
        logger.info(f"开始生成图案，提示词: {prompt}")
        
        # 生成图案
        image_data = pattern_generator.generate(prompt)
        if not image_data:
            logger.error("图案生成失败")
            return jsonify({'error': '图案生成失败，请重试'}), 500
            
        logger.info("图案生成成功")
        return jsonify({'image': image_data})
        
    except ValueError as e:
        logger.error(f"参数验证错误: {str(e)}")
        return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        logger.error(f"图案生成过程发生错误: {str(e)}")
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return jsonify({'error': '服务器内部错误，请稍后重试'}), 500

@app.route('/analyze_steps', methods=['POST'])
def analyze_steps():
    """分析剪纸步骤的API端点
    
    Returns:
        tuple: (JSON响应, HTTP状态码)
    """
    try:
        # 获取并验证图像数据
        if not request.is_json:
            logger.warning("请求格式不是JSON")
            return jsonify({'error': '请求格式必须是JSON'}), 400
            
        image_data = request.json.get('image')
        if not image_data:
            logger.error("未提供图像数据")
            return jsonify({'error': '请提供需要分析的图像'}), 400

        # 验证base64数据格式
        try:
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            # 验证base64数据是否有效
            decoded_data = base64.b64decode(image_data)
            if len(decoded_data) == 0:
                logger.error("图像数据为空")
                return jsonify({'error': '图像数据为空'}), 400
                
            # 验证图像数据是否有效
            try:
                image = Image.open(io.BytesIO(decoded_data))
                if image.size[0] == 0 or image.size[1] == 0:
                    logger.error("图像尺寸无效")
                    return jsonify({'error': '图像尺寸无效'}), 400
            except Exception as e:
                logger.error(f"图像数据无效: {str(e)}")
                return jsonify({'error': '图像数据无效'}), 400
                
        except Exception as e:
            logger.error(f"图像数据格式无效: {str(e)}")
            return jsonify({'error': '图像数据格式不正确'}), 400

        # 分析剪纸步骤
        logger.info("开始分析剪纸步骤")
        try:
            result = step_analyzer.analyze(image_data)
        except Exception as e:
            logger.error(f"步骤分析失败: {str(e)}")
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return jsonify({'error': f'步骤分析失败: {str(e)}'}), 500
        
        # 验证分析结果
        if not result:
            logger.warning("未能生成任何步骤")
            return jsonify({'error': '无法生成剪纸步骤'}), 400
            
        if not isinstance(result, dict):
            logger.error(f"步骤格式无效: {type(result)}")
            return jsonify({'error': '步骤数据格式错误'}), 500
            
        if 'steps' not in result:
            logger.error("步骤数据缺少steps字段")
            return jsonify({'error': '步骤数据格式错误'}), 500
            
        if not result['steps']:
            logger.warning("步骤列表为空")
            return jsonify({'error': '未能生成有效的剪纸步骤'}), 400
            
        if not isinstance(result['steps'], list):
            logger.error(f"steps字段类型错误: {type(result['steps'])}")
            return jsonify({'error': '步骤数据格式错误'}), 500
            
        logger.info(f"成功生成 {len(result['steps'])} 个剪纸步骤")
        return jsonify(result)
        
    except ValueError as e:
        logger.error(f"参数验证错误: {str(e)}")
        return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        logger.error(f"步骤分析过程发生错误: {str(e)}")
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return jsonify({'error': '服务器内部错误，请稍后重试'}), 500

@app.route('/send_to_arduino', methods=['POST'])
def send_to_arduino():
    """发送指令到Arduino的API端点
    
    Returns:
        tuple: (JSON响应, HTTP状态码)
    """
    try:
        # 验证请求格式
        if not request.is_json:
            logger.warning("请求格式不是JSON")
            return jsonify({'error': '请求格式必须是JSON'}), 400
            
        svg_data = request.json.get('svg_data')
        if not svg_data:
            logger.error("未提供SVG数据")
            return jsonify({'error': '请提供SVG绘图数据'}), 400

        # 发送SVG到Arduino
        logger.info("正在发送SVG绘图到Arduino")
        success = arduino_controller.send_svg(svg_data)
        
        if success:
            logger.info("SVG绘图发送成功")
            return jsonify({'message': 'SVG绘图已成功发送到机器'})
        else:
            logger.error("SVG绘图发送失败")
            return jsonify({'error': '无法发送SVG绘图到机器'}), 500
            
    except ValueError as e:
        logger.error(f"参数验证错误: {str(e)}")
        return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        logger.error(f"Arduino通信错误: {str(e)}")
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return jsonify({'error': '机器通信错误，请检查连接'}), 500

@app.route('/calibrate_machine', methods=['POST'])
def calibrate_machine():
    """校准机器的API端点
    
    Returns:
        tuple: (JSON响应, HTTP状态码)
    """
    try:
        logger.info("开始机器校准")
        success = arduino_controller.calibrate()
        
        if success:
            logger.info("机器校准成功")
            return jsonify({'message': '机器校准成功'})
        else:
            logger.error("机器校准失败")
            return jsonify({'error': '机器校准失败，请检查机器状态'}), 500
            
    except Exception as e:
        logger.error(f"校准过程发生错误: {str(e)}")
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return jsonify({'error': '校准过程出错，请重试'}), 500

@app.route('/test_connection', methods=['POST'])
def test_connection():
    """测试机器连接的API端点
    
    Returns:
        tuple: (JSON响应, HTTP状态码)
    """
    try:
        logger.info("开始测试机器连接")
        success = arduino_controller.test_connection()
        
        if success:
            logger.info("连接测试成功")
            return jsonify({'message': '机器连接正常'})
        else:
            logger.error("连接测试失败")
            return jsonify({'error': '无法连接到机器，请检查连接'}), 500
            
    except Exception as e:
        logger.error(f"连接测试错误: {str(e)}")
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return jsonify({'error': '连接测试失败，请检查机器状态'}), 500

@app.errorhandler(404)
def not_found(error):
    """处理404错误
    
    Args:
        error: 错误对象
        
    Returns:
        tuple: (JSON响应, HTTP状态码)
    """
    logger.warning(f"请求的页面不存在: {request.url}")
    return jsonify({'error': '请求的页面不存在'}), 404

@app.errorhandler(500)
def internal_error(error):
    """处理500错误
    
    Args:
        error: 错误对象
        
    Returns:
        tuple: (JSON响应, HTTP状态码)
    """
    logger.error(f"服务器内部错误: {str(error)}")
    logger.error(f"详细错误信息: {traceback.format_exc()}")
    return jsonify({'error': '服务器内部错误，请稍后重试'}), 500

if __name__ == '__main__':
    # 启动Flask应用
    logger.info("启动AI剪纸图案生成器服务")
    app.run(debug=False, host='0.0.0.0', port=5000) 