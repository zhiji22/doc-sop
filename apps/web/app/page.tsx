"use client"

import { Show, UserButton, SignInButton } from "@clerk/nextjs"

export default function Page() {
  return (
    <div style={{ padding: 24 }}>
      <Show when="signed-out">
        <SignInButton />
      </Show>

      <Show when="signed-in">
        <>
          <UserButton />
          <div style={{ marginTop: 16 }}>Logged in</div>
        </>
      </Show>
    </div>
  )
}