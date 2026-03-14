/**
 * Next.js 中间件（路由守卫）
 * 在请求到达页面之前执行，用于保护需要登录的路由。
 * /dashboard 及其子路由需要登录，未登录会自动跳转到 /sign-in。
 */
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"

// 定义需要登录保护的路由
const isProtectedRoute = createRouteMatcher(["/dashboard(.*)"])

export default clerkMiddleware(async (auth, req) => {
  // 如果访问的是受保护路由，强制要求登录
  if (isProtectedRoute(req)) {
    await auth.protect()
  }
})

// matcher 告诉 Next.js 哪些路径需要经过此中间件（排除静态资源和 _next 内部路径）
export const config = {
  matcher: ["/((?!_next|.*\\..*).*)"],
}

