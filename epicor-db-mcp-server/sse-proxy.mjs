#!/usr/bin/env node
/**
 * Minimal stdio-to-SSE MCP proxy.
 *
 * Connects to a remote SSE MCP server (with simple token auth) and exposes
 * it as a stdio MCP server that Cursor can launch directly.
 *
 * Usage (in .cursor/mcp.json):
 *   { "command": "node", "args": ["epicor-db-mcp-server/sse-proxy.mjs"] }
 *
 * Env vars (set in .cursor/mcp.json "env" or workspace .env):
 *   MCP_SSE_URL  — full SSE URL including token, e.g.
 *                  http://10.0.2.107:3100/sse?token=abc123
 */

import http from 'node:http';
import https from 'node:https';
import { URL } from 'node:url';

const SSE_URL = process.env.MCP_SSE_URL;
if (!SSE_URL) {
  process.stderr.write('ERROR: MCP_SSE_URL environment variable is required\n');
  process.exit(1);
}

const sseUrl = new URL(SSE_URL);
const httpMod = sseUrl.protocol === 'https:' ? https : http;

/** URL the server tells us to POST messages to (received via SSE "endpoint" event). */
let postEndpointUrl = null;

/** Buffer for incomplete SSE lines. */
let sseBuf = '';

// ── SSE connection ──────────────────────────────────────────────────────────

function connectSSE() {
  const req = httpMod.get(SSE_URL, { headers: { Accept: 'text/event-stream' } }, (res) => {
    if (res.statusCode !== 200) {
      process.stderr.write(`SSE connection failed: HTTP ${res.statusCode}\n`);
      process.exit(1);
    }
    process.stderr.write('SSE connected\n');

    res.setEncoding('utf-8');
    res.on('data', (chunk) => {
      sseBuf += chunk;
      processSSE();
    });
    res.on('end', () => {
      process.stderr.write('SSE stream ended, exiting\n');
      process.exit(0);
    });
  });

  req.on('error', (err) => {
    process.stderr.write(`SSE connection error: ${err.message}\n`);
    process.exit(1);
  });
}

function processSSE() {
  // SSE protocol: events separated by blank lines
  const parts = sseBuf.split('\n\n');
  // Last element is either empty or an incomplete event — keep it in the buffer
  sseBuf = parts.pop() || '';

  for (const block of parts) {
    let eventType = 'message';
    let data = '';

    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        data += line.slice(5).trim();
      }
    }

    if (eventType === 'endpoint') {
      // Server tells us where to POST messages.
      // The endpoint may be a relative path — resolve against the SSE origin.
      const raw = data.trim();
      try {
        postEndpointUrl = new URL(raw, sseUrl.origin).href;
      } catch {
        postEndpointUrl = `${sseUrl.origin}${raw}`;
      }
      // Carry the token to POST endpoint if server expects it
      const token = sseUrl.searchParams.get('token');
      if (token && !postEndpointUrl.includes('token=')) {
        const sep = postEndpointUrl.includes('?') ? '&' : '?';
        postEndpointUrl += `${sep}token=${token}`;
      }
      process.stderr.write(`POST endpoint: ${postEndpointUrl}\n`);
    } else if (eventType === 'message') {
      // Forward server→client JSON-RPC message to stdout
      if (data) {
        process.stdout.write(data + '\n');
      }
    }
  }
}

// ── Stdin → POST to server ──────────────────────────────────────────────────

let stdinBuf = '';

process.stdin.setEncoding('utf-8');
process.stdin.on('data', (chunk) => {
  stdinBuf += chunk;
  let nl;
  while ((nl = stdinBuf.indexOf('\n')) !== -1) {
    const line = stdinBuf.slice(0, nl).trim();
    stdinBuf = stdinBuf.slice(nl + 1);
    if (line) {
      postMessage(line);
    }
  }
});

process.stdin.on('end', () => {
  process.stderr.write('stdin closed, exiting\n');
  process.exit(0);
});

/** Serialize POSTs so we don't blast the server with concurrent requests. */
const postQueue = [];
let posting = false;

function postMessage(jsonLine) {
  if (!postEndpointUrl) {
    process.stderr.write('WARN: POST endpoint not yet received, queuing...\n');
    setTimeout(() => postMessage(jsonLine), 200);
    return;
  }
  postQueue.push(jsonLine);
  drainQueue();
}

async function drainQueue() {
  if (posting) return;
  posting = true;
  while (postQueue.length > 0) {
    const line = postQueue.shift();
    await doPost(line);
  }
  posting = false;
}

function doPost(jsonLine) {
  return new Promise((resolve) => {
    const url = new URL(postEndpointUrl);
    const mod = url.protocol === 'https:' ? https : http;
    const body = Buffer.from(jsonLine, 'utf-8');

    const req = mod.request(
      {
        method: 'POST',
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': body.length,
        },
      },
      (res) => {
        let resBody = '';
        res.on('data', (d) => { resBody += d; });
        res.on('end', () => {
          if (res.statusCode >= 400) {
            process.stderr.write(`POST error ${res.statusCode}: ${resBody}\n`);
          }
          resolve();
        });
      },
    );

    req.on('error', (err) => {
      process.stderr.write(`POST request error: ${err.message}\n`);
      resolve();
    });

    req.end(body);
  });
}

// ── Start ───────────────────────────────────────────────────────────────────
connectSSE();
