import redis
# 直接localhost访问，无需获取WSLIP
r = redis.Redis(host="172.26.117.121", port=6379,  decode_responses=True)
print(r.ping())