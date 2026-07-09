import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

app = FastAPI(title="量化看盘核心网关 - 事件驱动版")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

REDIS_HOST = '172.26.117.121'
redis_client = aioredis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# ==========================================
# 1. 历史分时数据 API (动态列表版本)
# ==========================================
@app.get("/api/v1/stock/{code}/trend")
async def get_stock_trend(code: str):
    """
    自适应读取由数据泵实时追加的今日动态 Tick 队列
    """
    # 🆕 从 Redis List 中完整拉取从 09:15 到当前秒的所有切片
    tick_strings = await redis_client.lrange(f"history_ticks_list:{code}", 0, -1)
    
    if tick_strings:
        # 将每一级字符解析回 JSON 对象
        trend_data = [json.loads(t) for t in tick_strings]
        return {"code": code, "data": trend_data}
    else:
        return {"code": code, "data": []}

# 2. 纯事件驱动 WebSocket
@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    # 监听两个频道：实时 Tick 流 和 异动警报
    await pubsub.subscribe("tick_stream", "alert_channel")
    
    try:
        while True:
            # 阻塞等待 Redis 的推送，没有任何 sleep，收到即发，极速响应！
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message:
                await websocket.send_text(message['data'])
                
            # 每隔一段时间顺便推一下全局快照，用于更新卡片的最新价和涨跌幅
            snapshot_raw = await redis_client.hgetall("realtime_quote")
            if snapshot_raw:
                snapshot = {k: json.loads(v) for k, v in snapshot_raw.items()}
                await websocket.send_json({"type": "snapshot", "data": snapshot})
                
    except WebSocketDisconnect:
        print("🔴 前端监控大屏已断开连接")
    finally:
        await pubsub.unsubscribe("tick_stream", "alert_channel")
        await pubsub.close()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)