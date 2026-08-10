// MCP stdio 单次调用助手：供 mcp_update.py 使用
import { spawn } from 'child_process';

const tool = process.env.MCP_TOOL;
const args = JSON.parse(process.env.MCP_ARGS || '{}');

const child = spawn('node', ['stock-mcp-server/index.js'], { stdio: ['pipe', 'pipe', 'pipe'] });
let buf = '';
let stderrLog = '';
let resolved = false;

child.stdout.on('data', (chunk) => {
  buf += chunk.toString();
  const lines = buf.split('\n');
  buf = lines.pop();
  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const msg = JSON.parse(line);
      if (msg.id === 1) {
        resolved = true;
        const text = msg.result?.content?.[0]?.text;
        try { process.stdout.write(text); }
        catch (e) { process.stdout.write(JSON.stringify(text)); }
        child.kill();
        process.exit(0);
      }
    } catch (e) {}
  }
});
child.stderr.on('data', (c) => { stderrLog += c.toString(); });
child.on('exit', (code) => {
  if (!resolved) { console.error('MCP 退出 code=' + code + ' stderr=' + stderrLog.slice(0, 300)); process.exit(1); }
});

setTimeout(() => {
  child.stdin.write(JSON.stringify({
    jsonrpc: '2.0', id: 1, method: 'tools/call',
    params: { name: tool, arguments: args },
  }) + '\n');
}, 1000);

setTimeout(() => { if (!resolved) { console.error('MCP 超时'); child.kill(); process.exit(1); } }, 50000);
