import React, { useState, useEffect } from 'react'
import { Loader2, AlertCircle, RefreshCw, Sparkles, MessageSquare, TrendingUp } from 'lucide-react'
import { API_URL } from '../../services/api'

// Color palette for charts
const CHART_COLORS = [
  '#6366f1', // indigo
  '#8b5cf6', // violet
  '#a855f7', // purple
  '#ec4899', // pink
  '#f43f5e', // rose
  '#f97316', // orange
  '#eab308', // yellow
  '#22c55e', // green
  '#14b8a6', // teal
  '#3b82f6', // blue
]

/**
 * AI Chat Analyzer Performance Dashboard
 *
 * Displays:
 * - Intent distribution (doughnut chart)
 * - Sentiment distribution (horizontal bars)
 * - Classification confidence metrics
 * - Recent activity trend
 */
const AIChatAnalytics = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [trends, setTrends] = useState([])
  const [intents, setIntents] = useState([])
  const [sentiments, setSentiments] = useState([])
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)

    try {
      const token = localStorage.getItem('auth-storage')
        ? JSON.parse(localStorage.getItem('auth-storage')).state?.token
        : ''

      const headers = { 'Authorization': `Bearer ${token}` }

      // Fetch all data in parallel
      const [metricsRes, trendsRes, intentsRes, sentimentsRes] = await Promise.all([
        fetch(`${API_URL}/ai/chat-analytics/metrics`, { headers }),
        fetch(`${API_URL}/ai/chat-analytics/trend?days=7`, { headers }),
        fetch(`${API_URL}/ai/chat-analytics/intents`, { headers }),
        fetch(`${API_URL}/ai/chat-analytics/sentiment`, { headers }),
      ])

      if (!metricsRes.ok || !trendsRes.ok || !intentsRes.ok || !sentimentsRes.ok) {
        throw new Error('Failed to fetch analytics data')
      }

      const metricsData = await metricsRes.json()
      const trendsData = await trendsRes.json()
      const intentsData = await intentsRes.json()
      const sentimentsData = await sentimentsRes.json()

      setMetrics(metricsData.data || {})
      setTrends(trendsData.data || [])
      setIntents(intentsData.data || [])
      setSentiments(sentimentsData.data || {})
      setLastUpdated(new Date().toLocaleTimeString())
    } catch (err) {
      setError(err.message || 'Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">Loading AI Analytics...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-xl p-6">
        <div className="flex items-center space-x-3">
          <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
          <div>
            <h3 className="font-semibold text-red-800 dark:text-red-300">Error Loading Analytics</h3>
            <p className="text-sm text-red-600 dark:text-red-400 mt-1">{error}</p>
          </div>
          <button
            onClick={fetchData}
            className="ml-auto px-3 py-1.5 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const totalMessages = metrics?.total_messages || 0
  const aiMessages = metrics?.ai_messages || 0
  const classifiedMessages = metrics?.classified_messages || 0
  const avgIntentConfidence = metrics?.intent_confidence?.average || 0
  const avgSentimentConfidence = metrics?.sentiment_confidence?.average || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-600" />
            AI Chat Analyzer Performance
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Real-time analytics from {totalMessages} chat messages • Last updated: {lastUpdated || 'Never'}
          </p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Messages"
          value={totalMessages}
          subtitle={`${aiMessages} AI, ${totalMessages - aiMessages} Human`}
          icon={<MessageSquare className="w-5 h-5" />}
          color="indigo"
        />
        <MetricCard
          title="AI Responses"
          value={aiMessages}
          subtitle={`${metrics?.ai_usage_rate || 0}% of total`}
          icon={<Sparkles className="w-5 h-5" />}
          color="purple"
        />
        <MetricCard
          title="Classification Rate"
          value={`${metrics?.classification_rate || 0}%`}
          subtitle={`${classifiedMessages} classified`}
          icon={<TrendingUp className="w-5 h-5" />}
          color="green"
        />
        <MetricCard
          title="Avg Confidence"
          value={`${(avgIntentConfidence * 100).toFixed(1)}%`}
          subtitle="Intent classification"
          icon={<Sparkles className="w-5 h-5" />}
          color="blue"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Intent Distribution */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Intent Distribution</h3>
          {intents.length > 0 ? (
            <div className="space-y-3">
              {intents.slice(0, 5).map((intent, idx) => (
                <div key={intent.intent}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 dark:text-gray-300 capitalize">{intent.intent}</span>
                    <span className="text-gray-500 dark:text-gray-400">{intent.count} ({intent.high_confidence_rate}%)</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${(intent.count / Math.max(...intents.map(i => i.count))) * 100}%`,
                        backgroundColor: CHART_COLORS[idx % CHART_COLORS.length]
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No intent data available yet" />
          )}
        </div>

        {/* Sentiment Distribution */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Sentiment Analysis</h3>
          {sentiments.length > 0 ? (
            <div className="space-y-3">
              {sentiments.map((sentiment, idx) => (
                <div key={sentiment.sentiment}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 dark:text-gray-300 capitalize">{sentiment.sentiment}</span>
                    <span className="text-gray-500 dark:text-gray-400">{sentiment.count} ({sentiment.percentage}%)</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${sentiment.percentage}%`,
                        backgroundColor: getSentimentColor(sentiment.sentiment)
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No sentiment data available yet" />
          )}
        </div>

        {/* Activity Trend */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Recent Activity (7 days)</h3>
          {trends.length > 0 ? (
            <div className="h-48 flex items-end justify-between gap-2">
              {trends.map((day, idx) => {
                const maxCount = Math.max(...trends.map(t => t.total_messages), 1)
                const height = (day.total_messages / maxCount) * 100
                return (
                  <div key={day.date} className="flex-1 flex flex-col items-center gap-2">
                    <div className="w-full relative" style={{ height: '120px' }}>
                      <div
                        className="absolute bottom-0 w-full bg-indigo-500 hover:bg-indigo-600 rounded-t transition-all"
                        style={{ height: `${height}%` }}
                      />
                      {/* Tooltip */}
                      <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 opacity-0 hover:opacity-100 bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap transition-opacity">
                        {day.total_messages} msgs
                      </div>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-gray-400 rotate-45 origin-top-left">
                      {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' })}
                    </span>
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState message="No activity data available" />
          )}
        </div>

        {/* Classification Confidence & Evaluation Metrics */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Classification Quality</h3>
          <div className="space-y-4">
            <ConfidenceMeter
              label="Intent Confidence"
              value={avgIntentConfidence}
              min={metrics?.intent_confidence?.min || 0}
              max={metrics?.intent_confidence?.max || 1}
              color="indigo"
            />
            <ConfidenceMeter
              label="Sentiment Confidence"
              value={avgSentimentConfidence}
              min={metrics?.sentiment_confidence?.min || 0}
              max={metrics?.sentiment_confidence?.max || 1}
              color="purple"
            />
            <div className="pt-4 border-t border-gray-200 dark:border-gray-800 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Evaluation Status</span>
                <span className={`font-medium ${(metrics?.evaluated || 0) > 0 ? 'text-green-600' : 'text-yellow-600'}`}>
                  {(metrics?.evaluated || 0) > 0 ? 'Evaluated' : 'Pending'}
                </span>
              </div>
              {/* Evaluation Metrics from Phase 6 */}
              {metrics?.intent_accuracy !== undefined && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-green-50 dark:bg-green-950/30 rounded-lg p-3">
                    <p className="text-xs text-gray-500 dark:text-gray-400">Intent Accuracy</p>
                    <p className="text-lg font-bold text-green-600 dark:text-green-400">
                      {(metrics.intent_accuracy * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-3">
                    <p className="text-xs text-gray-500 dark:text-gray-400">Sentiment Accuracy</p>
                    <p className="text-lg font-bold text-blue-600 dark:text-blue-400">
                      {(metrics.sentiment_accuracy * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="bg-purple-50 dark:bg-purple-950/30 rounded-lg p-3">
                    <p className="text-xs text-gray-500 dark:text-gray-400">Intent Macro F1</p>
                    <p className="text-lg font-bold text-purple-600 dark:text-purple-400">
                      {(metrics.intent_macro_f1 * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="bg-teal-50 dark:bg-teal-950/30 rounded-lg p-3">
                    <p className="text-xs text-gray-500 dark:text-gray-400">Sentiment Macro F1</p>
                    <p className="text-lg font-bold text-teal-600 dark:text-teal-400">
                      {(metrics.sentiment_macro_f1 * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>
              )}
              {metrics?.evaluated > 0 && (
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  Based on {metrics.evaluated} ground-truth verified test cases •
                  Evaluated: {new Date(metrics.last_evaluated * 1000).toLocaleString()}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Data Source Info */}
      <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" />
          <div>
            <h4 className="font-medium text-blue-900 dark:text-blue-200">Data Sources</h4>
            <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
              Live data from database ({totalMessages} messages) • Evaluation results from
              <code className="mx-1 px-1 py-0.5 bg-blue-100 dark:bg-blue-900 rounded text-xs">evaluation/results/</code>
              {metrics?.data_source !== 'none' && ` • Last eval: ${new Date(metrics?.last_evaluated * 1000).toLocaleDateString()}`}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// Helper components
function MetricCard({ title, value, subtitle, icon, color }) {
  const colorClasses = {
    indigo: 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400',
    purple: 'bg-purple-100 dark:bg-purple-900/40 text-purple-600 dark:text-purple-400',
    green: 'bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400',
    blue: 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400',
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{subtitle}</p>
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

function ConfidenceMeter({ label, value, min, max, color }) {
  const percentage = ((value - min) / (max - min || 1)) * 100

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600 dark:text-gray-400">{label}</span>
        <span className="font-medium text-gray-900 dark:text-white">{(value * 100).toFixed(1)}%</span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all ${
            color === 'indigo' ? 'bg-indigo-500' : 'bg-purple-500'
          }`}
          style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
        />
      </div>
    </div>
  )
}

function EmptyState({ message }) {
  return (
    <div className="flex flex-col items-center justify-center h-40 text-gray-400 dark:text-gray-600">
      <MessageSquare className="w-8 h-8 mb-2" />
      <p className="text-sm">{message}</p>
    </div>
  )
}

function getSentimentColor(sentiment) {
  const colors = {
    positive: '#22c55e',
    negative: '#ef4444',
    neutral: '#6b7280',
    happy: '#22c55e',
    sad: '#3b82f6',
    angry: '#ef4444',
    confused: '#f59e0b',
  }
  return colors[sentiment?.toLowerCase()] || '#6366f1'
}

export default AIChatAnalytics
