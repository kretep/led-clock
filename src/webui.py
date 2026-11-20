PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>LED Clock</title>
<style>
body{font-family:system-ui,sans-serif;margin:16px;max-width:560px;background:#111;color:#eee}
h1{font-size:22px;margin:0 0 4px}#t{color:#aaa;margin-bottom:16px}
button{margin:4px;padding:10px 14px;border-radius:8px;border:1px solid #444;background:#222;color:#eee;font-size:15px}
button.on{background:#e8a33a;color:#111;border-color:#e8a33a}input{width:100%}
</style></head><body>
<h1>LED Clock</h1><div id=t>...</div>
<label>Brightness <input id=b type=range min=0 max=1 step=0.01></label>
<div id=m></div>
<script>
const j=async(u,o)=>(await fetch(u,o)).json();
async function load(){const s=await j('/api/status');
t.textContent=(s.time||'time not synced')+' \\u00b7 '+s.mode+(s.night?' \\u00b7 night':'');
b.max=s.max_brightness;if(document.activeElement!==b)b.value=s.brightness;m.innerHTML='';
for(const n of s.modes){const e=document.createElement('button');e.textContent=n;
if(n==s.mode)e.className='on';e.onclick=async()=>{await j('/api/mode?name='+n,{method:'POST'});load()};m.append(e)}}
b.onchange=()=>j('/api/brightness?value='+b.value,{method:'POST'});
load();setInterval(load,5000);
</script></body></html>"""
