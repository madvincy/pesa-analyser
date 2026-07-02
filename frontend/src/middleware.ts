import { withAuth } from "next-auth/middleware"
import { NextResponse } from "next/server"

export default withAuth(
  function middleware(req) {
    const token = req.nextauth.token
    const isAuth = !!token
    const isAuthPage = req.nextUrl.pathname.startsWith('/auth')
    const isAdminPage = req.nextUrl.pathname.startsWith('/admin')
    const isDashboardPage = req.nextUrl.pathname.startsWith('/dashboard')

    // Redirect authenticated users away from auth pages
    if (isAuthPage && isAuth) {
      return NextResponse.redirect(new URL('/dashboard', req.url))
    }

    // Protect admin routes
    if (isAdminPage && !isAuth) {
      const signInUrl = new URL('/auth/signin', req.url)
      signInUrl.searchParams.set('callbackUrl', req.nextUrl.pathname)
      return NextResponse.redirect(signInUrl)
    }

    // Check admin role
    if (isAdminPage && isAuth && token.role !== 'admin' && token.role !== 'super_admin') {
      return NextResponse.redirect(new URL('/dashboard', req.url))
    }

    // Protect dashboard routes
    if (isDashboardPage && !isAuth) {
      const signInUrl = new URL('/auth/signin', req.url)
      signInUrl.searchParams.set('callbackUrl', req.nextUrl.pathname)
      return NextResponse.redirect(signInUrl)
    }

    return NextResponse.next()
  },
  {
    callbacks: {
      authorized: ({ token }) => true,
    },
  }
)

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/admin/:path*',
    '/api/analysis/:path*',
    '/api/upload/:path*',
    '/api/reports/:path*',
    '/api/user/:path*',
    '/api/admin/:path*',
  ]
}
