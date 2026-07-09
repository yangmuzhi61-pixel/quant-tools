# feishu_utils.py (Webhook地址写死版)

import requests
from datetime import datetime
import logging

# 初始化日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. 【核心改动】将Webhook地址直接在此处写死 ---
# 请将下面的URL替换为您自己的、固定的飞书机器人Webhook地址
_FEISHU_WEBHOOK_URL = 'https://www.feishu.cn/flow/api/trigger-webhook/9644c26d7dea911d9b584fdd6c2c5d6f'


# --- 2. 【核心改动】移除了 set_default_webhook 函数 ---
# ---    因为地址已经固定，不再需要配置函数    ---


def send_feishu_text(text_content: str, add_timestamp: bool = True) -> bool:
    """
    向一个固定的、预设的飞书Webhook地址发送纯文本消息。

    :param text_content: str, 要发送的文本内容。
    :param add_timestamp: bool, (可选) 是否自动添加时间戳，默认为True。
    :return: bool, True表示成功，False表示失败。
    """

    # --- 构造消息体 ---
    full_message = text_content
    if add_timestamp:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_message = f"【{current_time}】\n\n{text_content}"

    logging.info(f"准备向预设机器人发送消息: '{full_message[:70]}...'")

    message_body = {
        "msg_type": "text",
        "content": {
            "text": full_message
        }
    }

    headers = {'Content-Type': 'application/json'}

    # --- 发送请求并处理响应 ---
    try:
        response = requests.post(_FEISHU_WEBHOOK_URL, json=message_body, headers=headers, timeout=10)
        response.raise_for_status()

        response_json = response.json()
        if response_json.get('code') == 0:
            logging.info("飞书消息已成功发送！")
            return True
        else:
            logging.error(f"飞书消息发送失败，服务器返回: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"发送飞书消息时出现网络错误: {e}")
        return False
    except Exception as e:
        logging.error(f"发送飞书消息时出现未知错误: {e}")
        return False


# --- 使用示例 ---
if __name__ == '__main__':
    print("--- 正在直接调用模块函数进行测试 ---")

    # 无需任何配置，直接调用
    send_feishu_text("这是一条来自“地址写死版”工具模块的测试消息。")