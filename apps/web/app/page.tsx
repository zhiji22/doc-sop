/**
 * 首页（/）
 * 根据登录状态显示不同内容：
 *   未登录 → 显示「Sign In」按钮
 *   已登录 → 显示用户头像和「Logged in」提示
 */
"use client"

import { Show, UserButton, SignInButton } from "@clerk/nextjs"

export default function Page() {
  return (
    <div style={{ padding: 24 }}>
      {/* 未登录时：显示登录按钮 */}
      <Show when="signed-out">
        <SignInButton />
      </Show>

      {/* 已登录时：显示用户头像（Clerk 组件）*/}
      <Show when="signed-in">
        <>
          <UserButton />
          <div style={{ marginTop: 16 }}>Logged in</div>
        </>
      </Show>
    </div>
  )
}