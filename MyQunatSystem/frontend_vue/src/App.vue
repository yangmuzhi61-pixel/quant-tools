<template>
  <div class="dashboard">
    <header class="header">
      <div class="header-title">
        <h2>📈 量化监控终端 <span class="live-badge">● 实盘运行中</span></h2>
      </div>
      <div class="indexes">
        <div 
          v-for="(data, code) in indexData" 
          :key="code" 
          class="index-card"
          :class="[getColorClass(data.lastPrice, data.lastClose), { 'active-card': selectedCode === code }]"
          @click="selectStock(code)"
        >
          <div class="stock-name">{{ stockNameMap[code] || '未知标的' }}</div>
          <div class="code">{{ code }}</div>
          <div class="price">{{ (data.lastPrice || 0).toFixed(2) }}</div>
          <div class="pct">{{ calcPct(data.lastPrice, data.lastClose) }}%</div>
        </div>
      </div>
    </header>

    <main class="main-content">
      <div class="chart-section">
        <div class="chart-header">
          <h3> Bars 📊 {{ stockNameMap[selectedCode] || '未知标的' }} ({{ selectedCode }}) 专业分时</h3>
          <div class="realtime-info" v-if="indexData[selectedCode]">
            <span class="info-item">最新: <strong :class="getColorClass(indexData[selectedCode].lastPrice, indexData[selectedCode].lastClose)">{{ (indexData[selectedCode].lastPrice || 0).toFixed(2) }}</strong></span>
            <span class="info-item">成交量: <strong>{{ (indexData[selectedCode].volume / 100).toFixed(0) }} 手</strong></span>
            <span class="info-item">成交额: <strong>{{ (indexData[selectedCode].amount / 10000).toFixed(0) }} 万</strong></span>
          </div>
        </div>
        <div class="chart-container" ref="chartRef"></div>
      </div>
      
      <div class="alert-panel">
        <h3>🚨 实时异动雷达</h3>
        <ul class="alert-list">
          <li v-for="(alert, index) in alerts" :key="index">
            <span class="time">[{{ alert.time }}]</span>
            <span class="code" @click="selectStock(alert.code)">{{ stockNameMap[alert.code] || alert.code }}</span>
            <span class="msg">{{ alert.message }}</span>
          </li>
          <li v-if="alerts.length === 0" class="empty-alert">雷达监控中，暂无异动...</li>
        </ul>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

// 🆕 全局股票/指数指代名称静态映射字典
const stockNameMap = {
  '000001.SH': '上证指数',
  '399006.SZ': '创业板指',
  '000688.SH': '科创50',
  '603989.SH': '艾华集团',
  '002881.SZ': '美格智能',
  '601127.SH': '赛力斯'
}

const indexData = ref({})
const alerts = ref([])
const chartRef = ref(null)
const selectedCode = ref('603989.SH') 
let myChart = null
let ws = null

// 核心时序控制变量
let fullDayTimeline = []
let fetchedPrices = []
let globalLastClose = 0.01 // 存储绝对精准的昨收价作Y轴基准

// 生成全天固定的时间轴坐标 (09:15 到 15:00)
const generateFullDayTimeline = () => {
  const timeline = []
  const addRange = (startH, startM, endH, endM) => {
    let curr = new Date(2026, 0, 1, startH, startM, 0)
    const end = new Date(2026, 0, 1, endH, endM, 0)
    while (curr <= end) {
      timeline.push(`${curr.getHours().toString().padStart(2, '0')}:${curr.getMinutes().toString().padStart(2, '0')}`)
      curr.setMinutes(curr.getMinutes() + 1)
    }
  }
  addRange(9, 15, 11, 30) // 包含竞价段
  addRange(13, 0, 15, 0)
  return timeline
}
fullDayTimeline = generateFullDayTimeline()

// 判定不同板块的涨跌幅限制 (主板10%, 双创20%, 北交所30%)
const getLimitPercent = (code) => {
  if (code.startsWith('399006') || code.startsWith('000688')) return 20
  if (code.endsWith('.BJ')) return 30
  return 10
}

const calcPct = (current, prev) => {
  if (!current || !prev || prev === 0) return '0.00'
  return (((current - prev) / prev) * 100).toFixed(2)
}

const getColorClass = (current, prev) => {
  if (!current || !prev) return 'flat'
  return current > prev ? 'up' : (current < prev ? 'down' : 'flat')
}

const selectStock = async (code) => {
  selectedCode.value = code
  await fetchAndRenderChart(code)
}

const fetchAndRenderChart = async (code) => {
  await nextTick()
  if (!chartRef.value) return

  if (!myChart) myChart = echarts.init(chartRef.value)
  myChart.showLoading({ text: '同步实盘线...', color: '#e7a126', textColor: '#fff', maskColor: 'rgba(20,20,20,0.8)' })
  
  try {
    const res = await fetch(`http://localhost:8000/api/v1/stock/${code}/trend?t=${Date.now()}`)
    const json = await res.json()
    const rawData = json.data || []
    
    // 🆕 优先从历史 Tick 存量里抓取真实的昨收价，彻底消灭幅度计算不对的Bug
    globalLastClose = rawData.length > 0 && rawData[0].lastClose 
      ? rawData[0].lastClose 
      : (indexData.value[code]?.lastClose || 20)
      
    const limitPct = getLimitPercent(code)

    // 初始化全天数据容器为 null
    fetchedPrices = new Array(fullDayTimeline.length).fill(null)
    
    // 🆕 拦截技术：寻找当前已收到的最新实时数据的最大索引位置
    let maxRealIdx = -1
    rawData.forEach(item => {
      const shortTime = item.time.substring(0, 5)
      const idx = fullDayTimeline.indexOf(shortTime)
      if (idx !== -1) {
        fetchedPrices[idx] = item.price
        if (idx > maxRealIdx) maxRealIdx = idx
      }
    })

    // 🆕 核心改造：只向前平滑补充到最新 Tick 所在的索引，未来时段保持 null，绝不画线！
    let lastValidPrice = globalLastClose
    for (let i = 0; i <= maxRealIdx; i++) {
      if (fetchedPrices[i] !== null) {
        lastValidPrice = fetchedPrices[i]
      } else {
        fetchedPrices[i] = lastValidPrice
      }
    }

    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const p = params[0]
          if (p.value === null || p.value === undefined) return ''
          const pct = calcPct(p.value, globalLastClose)
          return `时间: ${p.name}<br/>价格: <b>${parseFloat(p.value).toFixed(2)}</b><br/>偏离: <span class="${pct >= 0 ? 'up' : 'down'}"><b>${pct}%</b></span>`
        }
      },
      grid: { left: '4%', right: '5%', bottom: '5%', top: '5%', containLabel: true },
      xAxis: {
        type: 'category',
        data: fullDayTimeline, // 🆕 固定撑满全天
        axisLine: { lineStyle: { color: '#555' } },
        axisLabel: { interval: 30, showMaxLabel: true }
      },
      yAxis: {
        type: 'value',
        scale: false,
        // Y轴以昨收为绝对中心线对称
        min: globalLastClose * (1 - limitPct / 100),
        max: globalLastClose * (1 + limitPct / 100),
        interval: (globalLastClose * (limitPct / 100)) / 2, 
        axisLine: { lineStyle: { color: '#555' } },
        splitLine: { lineStyle: { color: '#2a2a2a' } },
        axisLabel: {
          // 🆕 强制 Y 轴刻度标签百分比化显示
          formatter: (value) => {
            const p = calcPct(value, globalLastClose)
            return p > 0 ? `+${p}%` : `${p}%`
          },
          textStyle: {
            color: (value) => {
              const p = calcPct(value, globalLastClose)
              return p > 0 ? '#f6465d' : (p < 0 ? '#0ecb81' : '#848e9c')
            }
          }
        }
      },
      series: [{
        data: fetchedPrices,
        type: 'line',
        smooth: true,
        symbol: 'none', 
        connectNulls: true, // 🆕 新增：如果某一分钟完全没有Tick(比如午休)，曲线会自动跨空值连接，绝不断线
        lineStyle: { color: '#e7a126', width: 1.5 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(231, 161, 38, 0.15)' },
            { offset: 1, color: 'rgba(231, 161, 38, 0.0)' }
          ])
        }
      }]
    }
    myChart.setOption(option, true) 
  } catch (e) {
    console.error("分时图渲染失败", e)
  } finally {
    myChart.hideLoading()
  }
}

// 毫秒级增量缝合
const appendRealtimeTickToChart = (tickData) => {
  if (!myChart || !tickData.price) return

  const timeStr = tickData.time.substring(0, 5)
  const idx = fullDayTimeline.indexOf(timeStr)
  
  if (idx !== -1) {
    // 收到推送直接注入对应的时段格子
    fetchedPrices[idx] = tickData.price
    
    myChart.setOption({
      series: [{ data: fetchedPrices }]
    })
  }
}

const connectWS = () => {
  ws = new WebSocket('ws://localhost:8000/ws/realtime')
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    
    if (msg.type === 'new_tick') {
      if (msg.code === selectedCode.value) {
        appendRealtimeTickToChart(msg.data)
      }
    }
    else if (msg.type === 'snapshot') {
      indexData.value = msg.data
    } 
    else if (msg.type === 'surge') {
      alerts.value.unshift(msg)
      if (alerts.value.length > 15) alerts.value.pop()
    }
  }
}

onMounted(() => {
  fetchAndRenderChart(selectedCode.value)
  connectWS()
  window.addEventListener('resize', () => myChart?.resize())
})

onUnmounted(() => {
  if (ws) ws.close()
  myChart?.dispose()
})
</script>

<style scoped>
/* 极客深色交易终端 UI */
.dashboard { background: #0f1015; color: #d1d4dc; min-height: 100vh; padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
.header { border-bottom: 1px solid #232530; padding-bottom: 20px; margin-bottom: 20px;}
.header-title { display: flex; align-items: center; gap: 15px; margin-bottom: 15px; }
.header-title h2 { margin: 0; color: #fff; font-size: 20px; }
.live-badge { font-size: 12px; color: #00e676; background: rgba(0, 230, 118, 0.1); padding: 4px 8px; border-radius: 4px; border: 1px solid rgba(0, 230, 118, 0.3); }

.indexes { display: flex; gap: 15px; flex-wrap: wrap; }
.index-card { 
  background: #181a20; padding: 12px 20px; border-radius: 6px; 
  text-align: center; min-width: 140px; border: 1px solid #232530; 
  cursor: pointer; transition: all 0.2s;
}
.index-card:hover { border-color: #555; transform: translateY(-2px); }
.active-card { border-color: #e7a126 !important; background: #20222a; box-shadow: 0 0 10px rgba(231, 161, 38, 0.1); }

/* 🆕 强制高亮中文简称为首要信息 */
.stock-name { font-size: 15px; font-weight: bold; color: #fff; margin-bottom: 4px;}
.index-card .code { font-size: 11px; color: #848e9c; margin-bottom: 6px; font-family: monospace;}
.index-card .price { font-size: 20px; font-weight: bold; font-family: monospace;}
.index-card .pct { font-size: 13px; margin-top: 4px; font-family: monospace;}

.up { color: #f6465d; }      
.down { color: #0ecb81; }    
.flat { color: #848e9c; }

.main-content { display: flex; gap: 20px; height: calc(100vh - 180px); }
.chart-section { flex: 3; display: flex; flex-direction: column; background: #181a20; border-radius: 6px; border: 1px solid #232530; padding: 20px; }
.chart-header { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1px dashed #232530; padding-bottom: 10px; margin-bottom: 15px;}
.chart-header h3 { margin: 0; color: #fff; font-size: 18px; }
.realtime-info { display: flex; gap: 20px; font-size: 14px; color: #848e9c; }
.realtime-info strong { color: #fff; font-family: monospace; font-size: 16px;}
.chart-container { flex: 1; min-height: 400px; }

.alert-panel { flex: 1; background: #181a20; border-radius: 6px; border: 1px solid #232530; padding: 20px; display: flex; flex-direction: column; }
.alert-panel h3 { margin: 0 0 15px 0; color: #fff; font-size: 16px; border-bottom: 1px solid #232530; padding-bottom: 10px;}
.alert-list { list-style: none; padding: 0; margin: 0; overflow-y: auto; flex: 1; }
.alert-list li { margin-bottom: 12px; font-size: 13px; line-height: 1.4; padding-bottom: 8px; border-bottom: 1px dashed #232530;}
.alert-list .time { color: #848e9c; margin-right: 8px; font-family: monospace;}
.alert-list .code { font-weight: bold; color: #e7a126; margin-right: 8px; cursor: pointer; text-decoration: underline;}
.alert-list .msg { color: #f6465d; }
.empty-alert { color: #848e9c; text-align: center; margin-top: 20px; border: none !important;}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #181a20; }
::-webkit-scrollbar-thumb { background: #232530; border-radius: 3px; }
</style>