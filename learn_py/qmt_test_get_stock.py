import pandas as pd
from datetime import datetime
from xtquant import xtdata

def test_fetch_qmt_data():
    # 测试标的
    test_code = '603989.SH'
    
    # 构造时间参数 (获取今天的日期，例如 "20240520")
    today_str = datetime.now().strftime("%Y%m%d")
    
    # QMT 的时间格式要求：起止时间通常为 YYYYMMDD 或 YYYYMMDDHHMMSS
    # 我们设定起始时间为今天开盘 09:30:00
    start_time_str = f"{today_str}093000"
    
    # 截止时间可以直接留空，QMT 会默认拉取到最新，或者传当前时间
    # end_time_str = datetime.now().strftime("%Y%m%d%H%M%S")

    print(f"==================================================")
    print(f"🎯 正在测试 QMT 数据获取机制")
    print(f"📅 测试标的: {test_code} | 起始时间: {start_time_str}")
    print(f"==================================================\n")

    # ---------------------------------------------------------
    # 测试 1: 获取 1 分钟线 (1m)
    # ---------------------------------------------------------
    print("【测试 1】获取 1 分钟 K 线数据 (1m)")
    
    # 步骤 A: 先从券商服务器下载数据到本地
    print(" -> 正在执行 download_history_data (1m)...")
    xtdata.download_history_data(test_code, period='1m', start_time=start_time_str)
    
    # 步骤 B: 从本地读取刚才下载的数据
    print(" -> 正在执行 get_market_data_ex (1m)...")
    data_1m = xtdata.get_market_data_ex(
        field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
        stock_list=[test_code],
        period='1m',
        start_time=start_time_str
        # end_time 留空即可获取到最新
    )

    if test_code in data_1m and not data_1m[test_code].empty:
        df_1m = data_1m[test_code]
        print(f" ✅ 成功获取 1m 数据！共 {len(df_1m)} 条记录。")
        print(" ⬇️ 前 3 条数据预览：")
        print(df_1m.head(3))
    else:
        print(" ❌ 获取 1m 数据失败，返回为空。")

    print("\n" + "-"*50 + "\n")

    # ---------------------------------------------------------
    # 测试 2: 获取分笔数据 (Tick)
    # ---------------------------------------------------------
    print("【测试 2】获取逐笔数据 (Tick)")
    
    # 步骤 A: 下载 Tick 数据
    print(" -> 正在执行 download_history_data (tick)...")
    xtdata.download_history_data(test_code, period='tick', start_time=start_time_str)
    
    # 步骤 B: 读取 Tick 数据
    print(" -> 正在执行 get_market_data_ex (tick)...")
    data_tick = xtdata.get_market_data_ex(
        field_list=['time', 'lastPrice', 'volume', 'amount', 'askPrice1', 'bidPrice1'],
        stock_list=[test_code],
        period='tick',
        start_time=start_time_str
    )

    if test_code in data_tick:
        # Tick 数据根据不同 QMT 版本，返回的可能是 DataFrame 也可能是 Numpy 数组
        # 你的源码里写了：period为'tick'时返回 np.ndarray 或 pd.DataFrame
        tick_result = data_tick[test_code]
        
        # 统一转成 DataFrame 方便打印查看
        if not isinstance(tick_result, pd.DataFrame):
            df_tick = pd.DataFrame(tick_result)
        else:
            df_tick = tick_result
            
        if not df_tick.empty:
            print(f" ✅ 成功获取 Tick 数据！共 {len(df_tick)} 条记录。")
            print(" ⬇️ 尾部最新 3 条数据预览 (Latest Ticks)：")
            print(df_tick.tail(3))
        else:
            print(" ❌ 获取 Tick 数据失败，数据框为空。")
    else:
        print(" ❌ 获取 Tick 数据失败，字典中没有该股票代码。")
        
    print(f"\n==================================================")
    print("🏁 测试结束")

if __name__ == "__main__":
    test_fetch_qmt_data()