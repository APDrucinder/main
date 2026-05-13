import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server'
import { isClerkHandshakeSearch } from './lib/clerk-oauth-return'

const isPublicRoute = createRouteMatcher(['/', '/login(.*)'])
const signInUrl = '/login'
const signUpUrl = '/login'

export default clerkMiddleware(async (auth, req) => {
  if (req.nextUrl.pathname === '/dashboard' && isClerkHandshakeSearch(req.nextUrl.search)) {
    return NextResponse.next()
  }

  if (!isPublicRoute(req)) {
    const redirectUrl = new URL(signInUrl, req.url)
    redirectUrl.searchParams.set(
      'redirect_url',
      `${req.nextUrl.pathname}${req.nextUrl.search}`
    )

    await auth.protect({ unauthenticatedUrl: redirectUrl.toString() })
  }
}, {
  signInUrl,
  signUpUrl,
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
