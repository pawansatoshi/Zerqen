(() => {
  const TIMEFRAMES=["1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"];
  let chart=null,candleSeries=null,volumeSeries=null,ema9Series=null,ema21Series=null,rsiSeries=null;
  let lastChartData=null, chartReady=false, currentChartTf="1h";
  const $=id=>document.getElementById(id);
  const token=()=>sessionStorage.getItem("zerqen_token")||localStorage.getItem("zerqen_token")||"";
  const api=(path,options={})=>fetch(path,Object.assign({},options,{headers:Object.assign({},options.headers||{},{"x-zerqen-dashboard-token":token()})}));
  function money(v){if(v==null||v==="")return "—";return (Number(v)>=0?"+":"")+"$"+Number(v).toFixed(2)}
  function injectLibrary(){
    return new Promise((resolve,reject)=>{
      if(window.LightweightCharts)return resolve();
      const s=document.createElement("script");s.src="https://cdn.jsdelivr.net/npm/lightweight-charts@5.0.0/dist/lightweight-charts.standalone.production.js";s.onload=resolve;s.onerror=()=>reject(new Error("chart library unavailable"));document.head.appendChild(s);
    });
  }
  function buildToolbar(){
    const t=$("futuresChartTf"); if(!t)return;
    t.innerHTML=TIMEFRAMES.map(x=>"<button data-fchart-tf='"+x+"' class='"+(x===currentChartTf?"active":"")+"'>"+x.toUpperCase()+"</button>").join("");
    t.querySelectorAll("[data-fchart-tf]").forEach(b=>b.onclick=()=>loadFuturesChart(b.dataset.fchartTf));
  }
  function initChart(){
    if(chartReady||!window.LightweightCharts)return;
    const el=$("futuresChart");if(!el)return;
    chart=LightweightCharts.createChart(el,{autoSize:true,layout:{background:{type:"solid",color:"transparent"},textColor:"#8f98a8"},grid:{vertLines:{color:"rgba(255,255,255,.045)"},horzLines:{color:"rgba(255,255,255,.045)"}},rightPriceScale:{borderColor:"rgba(255,255,255,.08)"},timeScale:{borderColor:"rgba(255,255,255,.08)",timeVisible:true,secondsVisible:false},handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},handleScale:{mouseWheel:true,pinch:true,axisPressedMouseMove:true}});
    candleSeries=chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:"#53d98b",downColor:"#ff6b76",borderVisible:false,wickUpColor:"#53d98b",wickDownColor:"#ff6b76"});
    volumeSeries=chart.addSeries(LightweightCharts.HistogramSeries,{priceFormat:{type:"volume"},priceScaleId:"volume",scaleMargins:{top:.78,bottom:0}});
    volumeSeries.priceScale().applyOptions({scaleMargins:{top:.78,bottom:0}});
    ema9Series=chart.addSeries(LightweightCharts.LineSeries,{color:"#82aaff",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
    ema21Series=chart.addSeries(LightweightCharts.LineSeries,{color:"#f4c76b",lineWidth:1,priceLineVisible:false,lastValueVisible:false});
    rsiSeries=chart.addSeries(LightweightCharts.LineSeries,{color:"#c8ced8",lineWidth:1,priceLineVisible:false,lastValueVisible:false,pane:1});
    chartReady=true;
    const ro=new ResizeObserver(()=>chart.applyOptions({width:el.clientWidth,height:el.clientHeight}));ro.observe(el);
  }
  function applyMarkers(d){
    if(!candleSeries)return;
    const markers=[];
    (d.signals||[]).forEach(s=>markers.push({time:s.time,position:s.side==="BUY"?"belowBar":"aboveBar",color:s.side==="BUY"?"#53d98b":"#ff6b76",shape:s.side==="BUY"?"arrowUp":"arrowDown",text:s.side}));
    (d.trades||[]).forEach(t=>markers.push({time:t.time,position:t.side==="buy"?"belowBar":"aboveBar",color:"#82aaff",shape:"circle",text:t.type==="FUTURES_POSITION_CLOSED"?(Number(t.pnl||0)>=0?"PROFIT":"EXIT"):"ENTRY"}));
    if(window.LightweightCharts.createSeriesMarkers)LightweightCharts.createSeriesMarkers(candleSeries,markers.sort((a,b)=>a.time-b.time));
  }
  function setPositionLines(){
    if(!candleSeries||!lastChartData)return;
    const old=window.__zerqenFuturesPriceLines||[];old.forEach(x=>{try{candleSeries.removePriceLine(x)}catch(_){}});window.__zerqenFuturesPriceLines=[];
    const positions=window.__zerqenFuturesState?.positions||[];
    positions.forEach(p=>{
      const defs=[["entry_price","#82aaff","ENTRY"],["stop_price","#ff6b76","STOP"],["target_price","#53d98b","TARGET"],["liquidation_price","#f4c76b","LIQUIDATION"]];
      defs.forEach(([key,color,title])=>{const v=Number(p[key]);if(!Number.isFinite(v)||v<=0)return;const line=candleSeries.createPriceLine({price:v,color,lineWidth:1,lineStyle:2,axisLabelVisible:true,title});window.__zerqenFuturesPriceLines.push(line)});
    });
  }
  function renderStats(d){
    const last=Number(d.closes?.at(-1)||0),rsi=Number(d.rsi14?.at(-1)||0),atr=Number(d.atr14?.at(-1)||0),vol=Number(d.volumes?.at(-1)||0),vs=Number(d.volumeSma20?.at(-1)||0);
    if($("fChartPrice"))$("fChartPrice").textContent="$"+last.toLocaleString(undefined,{maximumFractionDigits:6});
    if($("fChartRsi"))$("fChartRsi").textContent=rsi.toFixed(1);
    if($("fChartAtr"))$("fChartAtr").textContent=atr?((atr/last)*100).toFixed(2)+"%":"—";
    if($("fChartVol"))$("fChartVol").textContent=vs?(vol/vs).toFixed(2)+"x":"—";
    if($("fChartState"))$("fChartState").textContent=(d.signals||[]).at(-1)?.side||"WAITING";
  }
  async function loadFuturesChart(tf=currentChartTf){
    currentChartTf=tf;buildToolbar();
    try{
      await injectLibrary();initChart();
      const symbol=($("futSymbol")?.value||"BTC/USDT").trim().toUpperCase();
      const r=await api("/api/futures-chart?symbol="+encodeURIComponent(symbol)+"&timeframe="+encodeURIComponent(tf)+"&limit=800",{cache:"no-store"});const d=await r.json();
      if(!r.ok||!d.ok)throw new Error(d.error||"chart data unavailable");
      lastChartData=d;
      const candles=d.times.map((t,i)=>({time:t,open:d.opens[i],high:d.highs[i],low:d.lows[i],close:d.closes[i]}));
      const vols=d.times.map((t,i)=>({time:t,value:d.volumes[i],color:d.closes[i]>=d.opens[i]?"rgba(83,217,139,.35)":"rgba(255,107,118,.35)"}));
      candleSeries.setData(candles);volumeSeries.setData(vols);
      ema9Series.setData(d.times.map((t,i)=>({time:t,value:d.ema9[i]})).filter(x=>Number.isFinite(x.value)));
      ema21Series.setData(d.times.map((t,i)=>({time:t,value:d.ema21[i]})).filter(x=>Number.isFinite(x.value)));
      rsiSeries.setData(d.times.map((t,i)=>({time:t,value:d.rsi14[i]})).filter(x=>Number.isFinite(x.value)));
      applyMarkers(d);renderStats(d);chart.timeScale().fitContent();
      $("futuresChartStatus").textContent="LIVE · "+tf.toUpperCase()+" · "+d.times.length+" candles";
      await refreshFuturesState();
    }catch(e){if($("futuresChartStatus"))$("futuresChartStatus").textContent="CHART ERROR · "+e.message}
  }
  async function refreshFuturesState(){
    try{const r=await api("/api/futures-paper",{cache:"no-store"});const d=await r.json();window.__zerqenFuturesState=d;if(d.ok&&d.initialized){if($("fChartEquity"))$("fChartEquity").textContent="$"+Number(d.equity).toFixed(2);if($("fChartTarget"))$("fChartTarget").textContent="$"+Number(d.daily_target).toFixed(2);if($("fChartDaily"))$("fChartDaily").textContent=money(d.daily_pnl);if($("fChartRisk"))$("fChartRisk").textContent=d.daily_target_hit?"TARGET LOCK":d.halted?"HALTED":"ARMED";}setPositionLines()}catch(_){}}
  function toggleSeries(key,el){const map={ema9:ema9Series,ema21:ema21Series,rsi:rsiSeries,volume:volumeSeries};const s=map[key];if(!s)return;s.applyOptions({visible:!s.options().visible});el.classList.toggle("active",s.options().visible)}
  function install(){
    const host=$("futuresChartHost");if(!host)return;
    host.innerHTML='<div class="card chart-card"><div class="chart-head"><div><div class="symbol" id="fChartSymbol">BTC/USDT · FUTURES</div><div class="price" id="fChartPrice">—</div><div class="sub"><span class="live"><i class="dot"></i><span id="futuresChartStatus">LOADING</span></span></div></div><div style="text-align:right"><div class="quote" id="fChartState">WAITING</div><div class="price">AI / risk signals</div></div></div><div id="futuresChart" style="height:520px;margin-top:10px"></div><div class="chart-tools" style="margin-top:8px" id="futuresChartTf"></div><div class="chart-tools" style="margin-top:7px"><button data-ind="ema9" class="active">EMA 9</button><button data-ind="ema21" class="active">EMA 21</button><button data-ind="volume" class="active">VOLUME</button><button data-ind="rsi" class="active">RSI 14</button><button id="fChartFit">FIT</button></div><div class="mini-grid"><div class="metric"><label>Equity</label><strong id="fChartEquity">—</strong></div><div class="metric"><label>Daily target</label><strong id="fChartTarget">—</strong></div><div class="metric"><label>Daily P&amp;L</label><strong id="fChartDaily">—</strong></div><div class="metric"><label>Engine</label><strong id="fChartRisk">—</strong></div><div class="metric"><label>RSI</label><strong id="fChartRsi">—</strong></div><div class="metric"><label>ATR</label><strong id="fChartAtr">—</strong></div><div class="metric"><label>Volume</label><strong id="fChartVol">—</strong></div></div><div class="note" style="margin-top:10px">Candles are Binance Futures public data. Green/red markers are deterministic research signals; blue markers and ENTRY/STOP/TARGET/LIQUIDATION lines reflect Zerqen paper state. No chart marker submits an order.</div></div>';
    buildToolbar();
    host.querySelectorAll("[data-ind]").forEach(b=>b.onclick=()=>toggleSeries(b.dataset.ind,b));
    $("fChartFit").onclick=()=>chart?.timeScale().fitContent();
    loadFuturesChart("1h");
    setInterval(refreshFuturesState,15000);
  }
  window.loadFuturesChart=loadFuturesChart;
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",install);else install();
})();