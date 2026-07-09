import time
import json
import redis
import pandas as pd
from datetime import datetime
from xtquant import xtdata

# ==========================================
# 1. 核心配置
# ==========================================
REDIS_HOST = '172.26.117.121'
r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

CODE_LIST = [
    '000001.SH', '399006.SZ', '000688.SH', 
    '002881.SZ', '603989.SH', '601127.SH'  
]
last_tick_prices = {}

# ==========================================
# 2. 启动时：初始化今日 Tick 队列 (使用 Redis 列表)
# ==========================================
def init_historical_ticks():
    print("📥 正在执行初始化：全量拉取今日历史 Tick 存量...")
    today_str = datetime.now().strftime("%Y%m%d")
    start_time_str = f"{today_str}091500" 
    
    try:
        for code in CODE_LIST:
            xtdata.download_history_data(code, period='tick', start_time=start_time_str)
            
        data_dict = xtdata.get_market_data_ex(
            field_list=['time', 'lastPrice', 'lastClose'], 
            stock_list=CODE_LIST, 
            period='tick', 
            start_time=start_time_str
        )
        
        for code, tick_data in data_dict.items():
            df = pd.DataFrame(tick_data) if not isinstance(tick_data, pd.DataFrame) else tick_data
            
            # 🆕 清空该股票在 Redis 中的旧队列，防止重复叠加
            r.delete(f"history_ticks_list:{code}")
            
            if not df.empty:
                trend_list = []
                for _, row in df.iterrows():
                    ts_ms = int(row['time'])
                    if ts_ms > 0:
                        time_str = datetime.fromtimestamp(ts_ms / 1000.0).strftime('%H:%M:%S')
                        trend_list.append(json.dumps({
                            "time": time_str, 
                            "price": float(row['lastPrice']),
                            "lastClose": float(row['lastClose'])
                        }))
                
                # 🆕 批量推入 Redis 列表尾部
                if trend_list:
                    r.rpush(f"history_ticks_list:{code}", *trend_list)
                
        print(f"✅ 历史存量队列初始化完毕！已成功注入 {len(CODE_LIST)} 只标的。")
    except Exception as e:
        print(f"⚠️ 初始化历史 Tick 失败，转为纯实盘模式。错误: {e}")

# ==========================================
# 3. 盘中：事件驱动 + 历史增量双写引擎
# ==========================================
def check_abnormal_movement(code, data):
    global last_tick_prices
    current_price = data.get('lastPrice', 0)
    last_close = data.get('lastClose', 0.01)
    prev_price = last_tick_prices.get(code, current_price)
    last_tick_prices[code] = current_price
    
    if current_price == 0: return False, ""
    messages = []
    if prev_price > 0:
        jump_ratio = (current_price - prev_price) / prev_price
        if jump_ratio > 0.005: messages.append(f"🚀 极速拉升！瞬跳 +{jump_ratio*100:.2f}%")
        elif jump_ratio < -0.005: messages.append(f"⚠️ 极速跳水！瞬跳 {jump_ratio*100:.2f}%")
            
    day_pct = (current_price - last_close) / last_close
    if 0.09 < day_pct < 0.11 or 0.19 < day_pct < 0.21: messages.append("🔥 逼近涨停板！资金正在强攻")
    elif -0.11 < day_pct < -0.09 or -0.21 < day_pct < -0.19: messages.append("🧊 逼近跌停板！注意承接风险")

    return (True, " | ".join(messages)) if messages else (False, "")

def on_data(datas):
    for code, data in datas.items():
        # 更新实盘快照
        r.hset("realtime_quote", code, json.dumps(data))
        
        tick_time = data.get('time', 0)
        time_str = datetime.fromtimestamp(tick_time / 1000.0).strftime('%H:%M:%S') if tick_time > 0 else datetime.now().strftime('%H:%M:%S')
        current_price = float(data.get('lastPrice', 0))
        last_close = float(data.get('lastClose', 0))
        
        if current_price <= 0: continue
        
        # 打包单体标准 Tick 结构
        tick_payload = {
            "time": time_str, 
            "price": current_price, 
            "lastClose": last_close
        }
        
        # 🆕 核心修正：除了广播，同步将当前最新的实盘 Tick 写入 Redis 历史队列
        # 这样历史池就会跟随实盘交易动态延长，彻底消灭历史断层！
        r.rpush(f"history_ticks_list:{code}", json.dumps(tick_payload))
        
        # 广播给前端
        tick_event = {
            "type": "new_tick",
            "code": code,
            "data": tick_payload
        }
        r.publish("tick_stream", json.dumps(tick_event))
        
        # 异动检测
        is_abnormal, msg = check_abnormal_movement(code, data)
        if is_abnormal:
            r.publish("alert_channel", json.dumps({"type": "surge", "code": code, "message": msg, "time": time_str}))

def main():
    print(f"🚀 启动分布式动态缝合数据泵 (Redis: {REDIS_HOST})...")
    init_historical_ticks()

    subscribe_id = xtdata.subscribe_whole_quote(CODE_LIST, callback=on_data)
    if subscribe_id > 0:
        print("🟢 系统进入实盘高频监控模式...\n")
        try:
            xtdata.run()
        except KeyboardInterrupt:
            pass
        finally:
            xtdata.unsubscribe_quote(subscribe_id)
    else:
        print("❌ 订阅失败")

if __name__ == "__main__":
    main()