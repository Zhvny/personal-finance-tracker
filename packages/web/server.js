import http from "node:http";
import https from "node:https";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 3000;
const API_TARGET = process.env.API_TARGET || "http://gateway:8444";

const MIME = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".wasm": "application/wasm",
};

function proxyRequest(req, clientRes) {
  const url = new URL(API_TARGET);
  console.log(`[PROXY] ${req.method} ${req.url} -> ${url.origin}${url.pathname}`);
  const proxyReq = http.request(
    {
      hostname: url.hostname,
      port: url.port,
      path: req.url,
      method: req.method,
      headers: {
        ...req.headers,
        host: url.hostname + ":" + url.port,
      },
    },
    (proxyRes) => {
      console.log(`[PROXY] ${req.method} ${req.url} <- ${proxyRes.statusCode}`);
      const hopByHop = new Set(["transfer-encoding", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "upgrade"]);
      const headers = {};
      for (const [key, value] of Object.entries(proxyRes.headers)) {
        if (!hopByHop.has(key.toLowerCase())) {
          headers[key] = value;
        }
      }
      clientRes.writeHead(proxyRes.statusCode, headers);
      const chunks = [];
      proxyRes.on('data', (chunk) => {
        chunks.push(chunk);
      });
      proxyRes.on('end', () => {
        const body = Buffer.concat(chunks);
        console.log(`[PROXY] ${req.method} ${req.url} response ended, body length: ${body.length}`);
        clientRes.end(body);
      });
      proxyRes.on('error', (err) => {
        console.error(`[PROXY RESP ERROR] ${req.method} ${req.url}: ${err.message}`);
        if (!clientRes.headersSent) {
          clientRes.writeHead(502);
        }
        clientRes.end(`Proxy response error: ${err.message}`);
      });
    }
  );
  proxyReq.on("error", (err) => {
    console.error(`[PROXY REQ ERROR] ${req.method} ${req.url}: ${err.message}`);
    if (!clientRes.headersSent) {
      clientRes.writeHead(502);
    }
    clientRes.end(`Proxy request error: ${err.message}`);
  });
  req.pipe(proxyReq);
}

function serveStatic(req, res) {
  let filePath = path.join(__dirname, "dist", req.url === "/" ? "index.html" : req.url);
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath);
    const contentType = MIME[ext] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": contentType });
    const stream = fs.createReadStream(filePath);
    stream.on("error", () => { if (!res.headersSent) res.writeHead(500); res.end(); });
    stream.pipe(res);
  } else {
    // SPA fallback to index.html. If the build output is missing/incomplete
    // (e.g. a failed rebuild wiped dist/), return 503 instead of piping a
    // nonexistent file — an unhandled ReadStream 'error' crashes the process
    // and sends the container into a restart loop.
    const indexPath = path.join(__dirname, "dist", "index.html");
    if (!fs.existsSync(indexPath)) {
      res.writeHead(503, { "Content-Type": "text/plain" });
      res.end("Service Unavailable: build output missing.");
      return;
    }
    res.writeHead(200, { "Content-Type": "text/html" });
    const stream = fs.createReadStream(indexPath);
    stream.on("error", () => { if (!res.headersSent) res.writeHead(503); res.end(); });
    stream.pipe(res);
  }
}

const server = http.createServer((req, res) => {
  console.log(`[SERVER] ${req.method} ${req.url}`);
  if (req.url.startsWith("/api")) {
    proxyRequest(req, res);
  } else {
    serveStatic(req, res);
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Web server on :${PORT}, proxying /api -> ${API_TARGET}`);
});
