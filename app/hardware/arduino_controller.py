import serial
import time
import os
import logging
import traceback
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET
import re

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ArduinoController:
    """ESP32 GRBL 两轴（X, Y）绘图控制器，支持舵机升降笔（M3 Sxx）"""
    
    def __init__(self):
        self.port = os.getenv('ARDUINO_SERIAL_PORT', 'COM3')
        self.baud_rate = int(os.getenv('ARDUINO_BAUD_RATE', 9600))
        self.serial = None
        self.timeout = float(os.getenv('ARDUINO_TIMEOUT', 2))
        self.max_retries = int(os.getenv('ARDUINO_MAX_RETRIES', 3))
        self.retry_delay = float(os.getenv('ARDUINO_RETRY_DELAY', 1))
        # 舵机角度
        self.pen_up_angle = 90
        self.pen_down_angle = 0
        self.rapid_feed_rate = 3000  # mm/分钟
        self.drawing_feed_rate = 1000  # mm/分钟
        self.pen_delay = 200  # 毫秒
        logger.info(f"ESP32 GRBL 控制器初始化，端口: {self.port}, 波特率: {self.baud_rate}")

    def connect(self) -> bool:
        if self.serial and self.serial.is_open:
            logger.info("已连接到 ESP32 GRBL")
            return True
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                logger.info(f"尝试连接 ESP32 GRBL，端口: {self.port}, 波特率: {self.baud_rate}")
                self.serial = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
                time.sleep(2)
                startup_message = self.serial.read_all().decode(errors='ignore').strip()
                if startup_message:
                    logger.info(f"GRBL 启动信息: {startup_message}")
                logger.info("成功连接到 ESP32 GRBL")
                return True
            except serial.SerialException as e:
                retry_count += 1
                logger.error(f"连接 ESP32 GRBL 失败（第 {retry_count}/{self.max_retries} 次）: {str(e)}")
                logger.error(f"详细错误: {traceback.format_exc()}")
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    self.serial = None
                    return False
            except Exception as e:
                logger.error(f"连接 ESP32 GRBL 时发生未知错误: {str(e)}")
                logger.error(f"详细错误: {traceback.format_exc()}")
                self.serial = None
                return False

    def disconnect(self) -> None:
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
                logger.info("已断开与 ESP32 GRBL 的连接")
            self.serial = None
        except Exception as e:
            logger.error(f"断开连接时出错: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            self.serial = None

    def _send_command(self, gcode_line: str) -> bool:
        if not self.serial or not self.serial.is_open:
            logger.error("无法发送指令：未连接到 ESP32 GRBL")
            return False
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                self.serial.write(f"{gcode_line}\n".encode())
                logger.debug(f"已发送: {gcode_line}")
                response_start_time = time.time()
                response = ""
                while time.time() - response_start_time < self.timeout:
                    if self.serial.in_waiting > 0:
                        response_part = self.serial.readline().decode(errors='ignore').strip()
                        response += response_part
                        if 'ok' in response.lower():
                            logger.debug(f"收到响应: {response}")
                            return True
                        if response_part:
                            logger.debug(f"部分响应: {response_part}")
                    time.sleep(0.01)
                retry_count += 1
                logger.warning(f"指令 '{gcode_line}' 超时或无 'ok' 响应（第 {retry_count}/{self.max_retries} 次）")
                logger.warning(f"完整响应: '{response}'")
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    return False
            except serial.SerialException as e:
                retry_count += 1
                logger.error(f"发送指令 '{gcode_line}' 时串口错误（第 {retry_count}/{self.max_retries} 次）: {str(e)}")
                logger.error(f"详细错误: {traceback.format_exc()}")
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    self.disconnect()
                    return False
            except Exception as e:
                logger.error(f"发送指令 '{gcode_line}' 时发生未知错误: {str(e)}")
                logger.error(f"详细错误: {traceback.format_exc()}")
                self.disconnect()
                return False

    def _parse_svg_path(self, path_data: str) -> List[Dict]:
        """解析 SVG 路径数据为 X、Y 绘图指令，支持绝对/相对 M、L、Z"""
        commands = []
        current_x = 0.0
        current_y = 0.0
        start_x = 0.0
        start_y = 0.0
        path_commands = re.findall(r'([MLZmlz])([^MLZmlz]*)', path_data)
        for cmd, params in path_commands:
            params = [float(p) for p in re.findall(r'[-+]?[0-9]*\.?[0-9]+', params)]
            if cmd == 'M':  # 绝对移动到
                current_x, current_y = params[0], params[1]
                start_x, start_y = current_x, current_y
                commands.append({'type': 'G0', 'x': current_x, 'y': current_y, 'f': self.rapid_feed_rate})
            elif cmd == 'm':  # 相对移动到
                current_x += params[0]
                current_y += params[1]
                start_x, start_y = current_x, current_y
                commands.append({'type': 'G0', 'x': current_x, 'y': current_y, 'f': self.rapid_feed_rate})
            elif cmd == 'L':  # 绝对直线到
                current_x, current_y = params[0], params[1]
                commands.append({'type': 'G1', 'x': current_x, 'y': current_y, 'f': self.drawing_feed_rate})
            elif cmd == 'l':  # 相对直线到
                current_x += params[0]
                current_y += params[1]
                commands.append({'type': 'G1', 'x': current_x, 'y': current_y, 'f': self.drawing_feed_rate})
            elif cmd in ['Z', 'z']:
                # 闭合路径，回到起点
                commands.append({'type': 'G1', 'x': start_x, 'y': start_y, 'f': self.drawing_feed_rate})
                current_x, current_y = start_x, start_y
        return commands

    def _command_to_gcode_string(self, command_dict: Dict) -> Optional[str]:
        try:
            cmd_type = command_dict.get('type')
            if cmd_type in ['G0', 'G1']:
                parts = [cmd_type]
                if 'x' in command_dict: parts.append(f"X{float(command_dict['x']):.3f}")
                if 'y' in command_dict: parts.append(f"Y{float(command_dict['y']):.3f}")
                if 'f' in command_dict: parts.append(f"F{int(command_dict['f'])}")
                return " ".join(parts)
            elif cmd_type == 'M3':
                return f"M3 S{command_dict['S']}"
            elif cmd_type == 'G4':
                return f"G4 P{command_dict['delay']}"
            else:
                logger.warning(f"不支持的指令类型: {cmd_type}")
                return None
        except Exception as e:
            logger.error(f"将指令转换为 G-code 时发生错误: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None

    def send_svg(self, svg_data: str) -> bool:
        if not self.serial:
            if not self.connect():
                logger.error("发送 SVG 失败：未连接到 ESP32 GRBL")
                return False
        try:
            logger.info("开始发送 SVG 绘图指令")
            root = ET.fromstring(svg_data)
            setup_commands = ["G21", "G90"]  # mm 单位，绝对定位
            for cmd_str in setup_commands:
                if not self._send_command(cmd_str):
                    logger.error(f"发送设置指令失败：{cmd_str}")
                    return False
            for path in root.findall(".//{http://www.w3.org/2000/svg}path"):
                path_data = path.get('d')
                if path_data:
                    commands = self._parse_svg_path(path_data)
                    # 抬笔
                    if not self._send_command(f"M3 S{self.pen_up_angle}"):
                        return False
                    time.sleep(self.pen_delay / 1000.0)
                    for cmd in commands:
                        gcode = self._command_to_gcode_string(cmd)
                        if gcode:
                            if not self._send_command(gcode):
                                logger.error(f"发送指令失败：{gcode}")
                                return False
                            # 画线时落笔，移动时抬笔
                            if cmd['type'] == 'G1':
                                if not self._send_command(f"M3 S{self.pen_down_angle}"):
                                    return False
                                time.sleep(self.pen_delay / 1000.0)
                            elif cmd['type'] == 'G0':
                                if not self._send_command(f"M3 S{self.pen_up_angle}"):
                                    return False
                                time.sleep(self.pen_delay / 1000.0)
            logger.info("成功发送所有 SVG 绘图指令")
            return True
        except Exception as e:
            logger.error(f"发送 SVG 时发生错误: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False

    def calibrate(self) -> bool:
        if not self.serial:
            if not self.connect():
                logger.error("校准失败：未连接到 ESP32 GRBL")
                return False
        try:
            calibration_command = "G28"  # 回原点
            logger.info(f"发送校准指令: {calibration_command}")
            if self._send_command(calibration_command):
                logger.info("ESP32 GRBL 确认校准指令")
                return True
            else:
                logger.warning("校准指令失败或未收到确认")
                return False
        except Exception as e:
            logger.error(f"校准时发生错误: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False

    def test_connection(self) -> bool:
        logger.info("测试 ESP32 GRBL 连接...")
        try:
            if self.connect():
                logger.info("ESP32 GRBL 连接测试成功")
                self.disconnect()
                return True
            else:
                logger.error("ESP32 GRBL 连接测试失败")
                return False
        except Exception as e:
            logger.error(f"连接测试时发生错误: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False