const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = 4000;

// 🔥 여기 주의! express.json() 사용하지 않음

app.use('/api/run', (req, res, next) => {
  console.log('📦 /api/run 요청 수신');
  next();
});

app.use(
  '/api',
  createProxyMiddleware({
    target: 'http://localhost:5050',
    changeOrigin: true,
    pathRewrite: { '^/api': '' },
    selfHandleResponse: false,
    onProxyReq: (proxyReq, req, res) => {
      let bodyData = '';

      req.on('data', chunk => {
        bodyData += chunk;
      });

      req.on('end', () => {
        if (bodyData) {
          proxyReq.setHeader('Content-Type', 'application/json');
          proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
          proxyReq.write(bodyData);
          proxyReq.end();
        }
      });
    }
  })
);

app.listen(PORT, () => {
  console.log(`🌐 프록시 서버 실행 중: http://localhost:${PORT}`);
});
