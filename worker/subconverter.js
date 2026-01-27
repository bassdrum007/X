/**
 * Cloudflare Worker - 订阅转换服务
 * 自动套用你的 Z.ini 配置
 * 
 * 部署后访问 Worker 地址即可使用
 */

const CONFIG = {
  // SubConverter 后端（使用公共后端，也可以换成自建的）
  backend: 'https://sub.xeton.dev',
  // 你的自定义配置文件
  config: 'https://raw.githubusercontent.com/bassdrum007/X/master/Z.ini',
};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    // 首页 - 显示使用说明
    if (path === '/' || path === '') {
      return new Response(getIndexHtml(url.origin), {
        headers: { 'Content-Type': 'text/html; charset=utf-8' }
      });
    }

    // 转换 API
    if (path === '/sub') {
      return handleSub(url);
    }

    // 短链接格式: /s/base64编码的订阅链接
    if (path.startsWith('/s/')) {
      const encoded = path.slice(3);
      try {
        const subUrl = atob(encoded);
        url.searchParams.set('url', subUrl);
        return handleSub(url);
      } catch {
        return new Response('Invalid short link', { status: 400 });
      }
    }

    return new Response('Not Found', { status: 404 });
  }
};

async function handleSub(url) {
  const subUrl = url.searchParams.get('url');
  if (!subUrl) {
    return new Response('Missing url parameter', { status: 400 });
  }

  // 构建 SubConverter 请求
  const target = url.searchParams.get('target') || 'clash';
  const converterUrl = new URL('/sub', CONFIG.backend);
  converterUrl.searchParams.set('target', target);
  converterUrl.searchParams.set('url', subUrl);
  converterUrl.searchParams.set('config', CONFIG.config);
  
  // 可选参数透传
  const optionalParams = [
    'include', 'exclude', 'emoji', 'list', 'udp', 'tfo', 
    'rename', 'sort', 'new_name', 'filename'
  ];
  optionalParams.forEach(param => {
    if (url.searchParams.has(param)) {
      converterUrl.searchParams.set(param, url.searchParams.get(param));
    }
  });

  try {
    // 请求后端
    const response = await fetch(converterUrl.toString(), {
      headers: {
        'User-Agent': 'ClashForAndroid/2.5.12'
      }
    });
    
    if (!response.ok) {
      return new Response('Backend error: ' + response.status, { status: 502 });
    }

    const body = await response.text();
    const filename = url.searchParams.get('filename') || 'clash';

    return new Response(body, {
      headers: {
        'Content-Type': 'text/yaml; charset=utf-8',
        'Content-Disposition': `attachment; filename="${filename}.yaml"`,
        'Cache-Control': 'no-cache',
        'Access-Control-Allow-Origin': '*',
      }
    });
  } catch (err) {
    return new Response('Fetch error: ' + err.message, { status: 500 });
  }
}

function getIndexHtml(origin) {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>🚀 订阅转换服务</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 800px;
      margin: 0 auto;
      padding: 40px 20px;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      min-height: 100vh;
      color: #e0e0e0;
    }
    h1 { 
      color: #fff; 
      text-align: center;
      font-size: 2em;
      margin-bottom: 10px;
    }
    .subtitle {
      text-align: center;
      color: #888;
      margin-bottom: 30px;
    }
    .card {
      background: rgba(255,255,255,0.05);
      border-radius: 16px;
      padding: 25px;
      margin-bottom: 20px;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
    }
    h3 { color: #4fc3f7; margin-top: 0; }
    code { 
      background: rgba(79, 195, 247, 0.2); 
      padding: 2px 8px; 
      border-radius: 4px;
      color: #4fc3f7;
    }
    pre { 
      background: rgba(0,0,0,0.3); 
      padding: 15px; 
      border-radius: 8px; 
      overflow-x: auto;
      color: #81c784;
    }
    input, select {
      width: 100%;
      padding: 12px 15px;
      font-size: 16px;
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 8px;
      background: rgba(255,255,255,0.1);
      color: #fff;
      margin-bottom: 15px;
    }
    input::placeholder { color: #888; }
    input:focus, select:focus {
      outline: none;
      border-color: #4fc3f7;
    }
    button {
      width: 100%;
      padding: 14px;
      font-size: 16px;
      font-weight: 600;
      background: linear-gradient(135deg, #4fc3f7 0%, #0288d1 100%);
      color: white;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 20px rgba(79, 195, 247, 0.4);
    }
    .copy-btn {
      width: auto;
      padding: 8px 16px;
      font-size: 14px;
      margin-top: 10px;
    }
    #result {
      margin-top: 20px;
      word-break: break-all;
    }
    #result pre {
      color: #fff;
      background: rgba(79, 195, 247, 0.1);
      border: 1px solid rgba(79, 195, 247, 0.3);
    }
    .success { color: #81c784; }
    ul { padding-left: 20px; }
    li { margin-bottom: 8px; }
    .footer {
      text-align: center;
      color: #666;
      margin-top: 40px;
      font-size: 14px;
    }
    .row {
      display: flex;
      gap: 15px;
    }
    .row > * { flex: 1; }
    @media (max-width: 600px) {
      .row { flex-direction: column; }
    }
  </style>
</head>
<body>
  <h1>🚀 订阅转换服务</h1>
  <p class="subtitle">自动套用 <code>Z.ini</code> 分流规则</p>
  
  <div class="card">
    <h3>⚡ 快速转换</h3>
    <input type="text" id="subUrl" placeholder="粘贴你的机场订阅链接...">
    <div class="row">
      <select id="target">
        <option value="clash">Clash</option>
        <option value="clashr">ClashR</option>
        <option value="surge">Surge 4</option>
        <option value="quan">Quantumult</option>
        <option value="quanx">Quantumult X</option>
        <option value="loon">Loon</option>
        <option value="v2ray">V2Ray</option>
      </select>
      <input type="text" id="filename" placeholder="文件名 (可选)">
    </div>
    <button onclick="convert()">生成订阅链接 ✨</button>
    <div id="result"></div>
  </div>

  <div class="card">
    <h3>📡 API 使用</h3>
    <pre>GET ${origin}/sub?url=你的订阅链接</pre>
  </div>
  
  <div class="card">
    <h3>⚙️ 可选参数</h3>
    <ul>
      <li><code>target</code> - 目标类型 (clash/surge/quanx/loon/v2ray)</li>
      <li><code>include</code> - 只保留匹配的节点 (正则)</li>
      <li><code>exclude</code> - 排除匹配的节点 (正则)</li>
      <li><code>emoji</code> - 添加国旗 emoji (true/false)</li>
      <li><code>rename</code> - 重命名规则</li>
      <li><code>filename</code> - 下载文件名</li>
    </ul>
  </div>

  <p class="footer">Powered by Cloudflare Workers</p>

  <script>
    function convert() {
      const subUrl = document.getElementById('subUrl').value.trim();
      if (!subUrl) { alert('请输入订阅链接'); return; }
      
      const target = document.getElementById('target').value;
      const filename = document.getElementById('filename').value.trim();
      
      let resultUrl = '${origin}/sub?url=' + encodeURIComponent(subUrl);
      if (target !== 'clash') resultUrl += '&target=' + target;
      if (filename) resultUrl += '&filename=' + encodeURIComponent(filename);
      
      document.getElementById('result').innerHTML = 
        '<p class="success">✅ 你的订阅链接：</p>' +
        '<pre>' + resultUrl + '</pre>' +
        '<button class="copy-btn" onclick="copyUrl()">📋 复制链接</button>';
      
      window.generatedUrl = resultUrl;
    }
    
    function copyUrl() {
      navigator.clipboard.writeText(window.generatedUrl).then(() => {
        const btn = document.querySelector('.copy-btn');
        btn.textContent = '✅ 已复制';
        setTimeout(() => { btn.textContent = '📋 复制链接'; }, 2000);
      });
    }
  </script>
</body>
</html>`;
}
