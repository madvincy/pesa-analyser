import { NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

export async function DELETE(request: Request) {
  try {
    const token = await getToken({ req: request as any })
    
    if (!token) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      )
    }

    const body = await request.json()
    const { confirm } = body

    if (!confirm) {
      return NextResponse.json(
        { error: 'Confirmation required' },
        { status: 400 }
      )
    }

    // In a real app, delete user data from database
    // For now, just return success
    return NextResponse.json({
      message: 'All user data deleted successfully'
    })
  } catch (error) {
    console.error('Delete data error:', error)
    return NextResponse.json(
      { error: 'Failed to delete data' },
      { status: 500 }
    )
  }
}
