# RatingGuard Frontend

Next.js TypeScript 前端（待开发）。

## 目录规划

```
frontend/
├── src/
│   ├── app/              # App Router 页面
│   │   ├── layout.tsx
│   │   ├── page.tsx       # 仪表盘主页
│   │   └── reviews/       # 评论列表 / 详情页
│   ├── components/        # 可复用 UI 组件
│   │   ├── ReviewCard.tsx
│   │   ├── AnalysisPanel.tsx
│   │   └── ReplyEditor.tsx
│   └── lib/               # API 客户端、工具函数
│       └── api.ts
├── package.json
├── tsconfig.json
└── next.config.js
```
