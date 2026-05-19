# RatingGuard Frontend

基于 **Next.js 14** (App Router) + **Tailwind CSS 3.4** 的 SaaS 面板。

## 目录结构

```
src/
├── app/
│   ├── layout.tsx       # 根布局（深色模式）
│   ├── page.tsx         # 主面板（双栏布局 + 手动/爬取两种输入模式）
│   └── globals.css      # 全局样式、骨架屏、打字机动画
├── hooks/
│   ├── useRecoveryStream.ts  # SSE 流式接收 React Hook
│   └── useReviews.ts         # 评论状态管理
└── lib/
    └── api.ts               # 统一 API 客户端
```

## 开发

```bash
npm run dev     # http://localhost:3000
npm run build   # 生产构建
npm run lint    # ESLint
```
