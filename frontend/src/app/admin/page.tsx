'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { 
  Users, FileText, CreditCard, MessageSquare, 
  TrendingUp, Activity, AlertCircle, CheckCircle,
  DollarSign, BarChart3, Clock, Zap
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, BarChart, Bar,
  PieChart, Pie, Cell, Legend
} from 'recharts'

export default function AdminDashboard() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [analytics, setAnalytics] = useState<any>(null)

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/auth/signin')
      return
    }

    if (session?.user?.role !== 'admin' && session?.user?.role !== 'super_admin') {
      router.push('/dashboard')
      return
    }

    fetchAnalytics()
  }, [status, session, router])

  const fetchAnalytics = async () => {
    try {
      const response = await fetch('/api/admin/analytics')
      const data = await response.json()
      setAnalytics(data)
    } catch (error) {
      console.error('Failed to fetch analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (!analytics) return null

  const stats = [
    {
      title: 'Total Users',
      value: analytics.users.total,
      icon: Users,
      color: 'text-blue-500',
      bg: 'bg-blue-500/10',
      change: `+${analytics.users.newToday} today`
    },
    {
      title: 'Analyses',
      value: analytics.analyses.total,
      icon: FileText,
      color: 'text-green-500',
      bg: 'bg-green-500/10',
      change: `${analytics.analyses.completed} completed`
    },
    {
      title: 'Revenue',
      value: `KES ${analytics.payments.revenue.toLocaleString()}`,
      icon: DollarSign,
      color: 'text-emerald-500',
      bg: 'bg-emerald-500/10',
      change: `${analytics.payments.successful} payments`
    },
    {
      title: 'Pending Messages',
      value: analytics.pendingMessages,
      icon: MessageSquare,
      color: 'text-yellow-500',
      bg: 'bg-yellow-500/10',
      change: 'Needs attention'
    }
  ]

  const statusData = [
    { name: 'Completed', value: analytics.analyses.completed },
    { name: 'Failed', value: analytics.analyses.failed },
    { name: 'Pending', value: analytics.analyses.total - analytics.analyses.completed - analytics.analyses.failed }
  ]

  const COLORS = ['#22c55e', '#ef4444', '#eab308']

  const paymentData = [
    { name: 'Successful', value: analytics.payments.successful },
    { name: 'Failed', value: analytics.payments.failed }
  ]

  const PAYMENT_COLORS = ['#22c55e', '#ef4444']

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div>
        <h1 className="text-3xl font-bold font-playfair">Admin Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome back, {session?.user?.name}! Here&apos;s your overview.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title} className="border-0 shadow-lg">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className={`p-3 rounded-full ${stat.bg}`}>
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
                <span className="text-xs text-muted-foreground">{stat.change}</span>
              </div>
              <div className="mt-4">
                <p className="text-sm text-muted-foreground">{stat.title}</p>
                <p className="text-2xl font-bold">{stat.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Analysis Status</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  fill="#8884d8"
                  paddingAngle={5}
                  dataKey="value"
                >
                  {statusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Payment Status</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={paymentData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  fill="#8884d8"
                  paddingAngle={5}
                  dataKey="value"
                >
                  {paymentData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={PAYMENT_COLORS[index % PAYMENT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Token Usage */}
      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Token & Prompt Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 bg-blue-500/10 rounded-lg text-center">
              <p className="text-sm text-muted-foreground">Total Tokens</p>
              <p className="text-2xl font-bold text-blue-500">
                {analytics.tokenUsage.totalTokens.toLocaleString()}
              </p>
            </div>
            <div className="p-4 bg-green-500/10 rounded-lg text-center">
              <p className="text-sm text-muted-foreground">Total Prompts</p>
              <p className="text-2xl font-bold text-green-500">
                {analytics.tokenUsage.totalPrompts}
              </p>
            </div>
            <div className="p-4 bg-red-500/10 rounded-lg text-center">
              <p className="text-sm text-muted-foreground">Failed Prompts</p>
              <p className="text-2xl font-bold text-red-500">
                {analytics.tokenUsage.totalFailed}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Recent Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics.users.recent.map((user: any) => (
                <div key={user.id} className="flex items-center justify-between p-2 hover:bg-muted rounded-lg">
                  <div>
                    <p className="font-medium">{user.name || 'Unknown'}</p>
                    <p className="text-sm text-muted-foreground">{user.email}</p>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(user.createdAt).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Recent Analyses</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics.analyses.recent.map((analysis: any) => (
                <div key={analysis.id} className="flex items-center justify-between p-2 hover:bg-muted rounded-lg">
                  <div>
                    <p className="font-medium">{analysis.fileName}</p>
                    <p className="text-sm text-muted-foreground">
                      {analysis.user?.name || 'Unknown'} • {analysis.status}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(analysis.createdAt).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
