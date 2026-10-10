import React, { useEffect, useState } from 'react'
import { 
  ClipboardList, 
  Search, 
  Filter, 
  RefreshCw, 
  ChevronLeft, 
  ChevronRight, 
  CheckCircle2, 
  XCircle, 
  AlertCircle,
  Eye,
  X
} from 'lucide-react'
import { adminService } from '../../services/adminService'
import toast from 'react-hot-toast'

function AuditLogs() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [limit] = useState(25)
  const [offset, setOffset] = useState(0)
  const [isLoading, setIsLoading] = useState(false)

  // Filters
  const [actionFilter, setActionFilter] = useState('')
  const [targetTypeFilter, setTargetTypeFilter] = useState('')
  const [outcomeFilter, setOutcomeFilter] = useState('')
  const [actorEmail, setActorEmail] = useState('')

  // Detail Modal
  const [activeDetailLog, setActiveDetailLog] = useState(null)

  const fetchLogs = async () => {
    setIsLoading(true)
    try {
      const params = {
        limit,
        offset,
        action: actionFilter.trim() || undefined,
        target_type: targetTypeFilter || undefined,
        outcome: outcomeFilter || undefined,
        actor_email: actorEmail.trim() || undefined,
      }
      const data = await adminService.getAuditLogs(params)
      setLogs(data.items || [])
      setTotal(data.total || 0)
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to fetch audit logs')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [offset, targetTypeFilter, outcomeFilter])

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    setOffset(0)
    fetchLogs()
  }

  const getOutcomeBadge = (outcome) => {
    const norm = String(outcome).toUpperCase()
    if (norm === 'SUCCESS') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>Success</span>
        </span>
      )
    }
    if (norm === 'FAILURE') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">
          <XCircle className="w-3.5 h-3.5" />
          <span>Failure</span>
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">
        <AlertCircle className="w-3.5 h-3.5" />
        <span>{outcome}</span>
      </span>
    )
  }

  const getActionBadge = (action) => {
    const act = String(action).toUpperCase()
    let color = 'bg-blue-100 text-blue-700 border-blue-200'
    if (act.includes('DELETE')) {
      color = 'bg-red-100 text-red-700 border-red-200'
    } else if (act.includes('ROLE')) {
      color = 'bg-purple-100 text-purple-700 border-purple-200'
    } else if (act.includes('STATUS')) {
      color = 'bg-amber-100 text-amber-700 border-amber-200'
    }
    return (
      <span className={`px-2 py-0.5 text-xs font-mono font-medium rounded border ${color}`}>
        {action}
      </span>
    )
  }

  const currentPage = Math.floor(offset / limit) + 1
  const totalPages = Math.ceil(total / limit) || 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <ClipboardList className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />
            <span>System Audit Logs</span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Immutable administrative and security event records for institutional governance.
          </p>
        </div>
        <button
          onClick={fetchLogs}
          className="px-3.5 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 flex items-center gap-2 font-medium shadow-sm transition-colors self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col md:flex-row items-center gap-4">
        <form onSubmit={handleSearchSubmit} className="flex-1 w-full flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              placeholder="Search by action (e.g. USER_ROLE_UPDATE, FILE_DELETE)..."
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-indigo-500"
            />
            <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" />
          </div>

          <div className="relative flex-1">
            <input
              type="text"
              placeholder="Filter by actor email..."
              value={actorEmail}
              onChange={(e) => setActorEmail(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-indigo-500"
            />
            <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" />
          </div>

          <button
            type="submit"
            className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors"
          >
            Apply
          </button>
        </form>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <select
            value={targetTypeFilter}
            onChange={(e) => { setTargetTypeFilter(e.target.value); setOffset(0); }}
            className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          >
            <option value="">All Target Types</option>
            <option value="user">User</option>
            <option value="file">File</option>
            <option value="circular">Circular</option>
          </select>

          <select
            value={outcomeFilter}
            onChange={(e) => { setOutcomeFilter(e.target.value); setOffset(0); }}
            className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          >
            <option value="">All Outcomes</option>
            <option value="SUCCESS">Success</option>
            <option value="FAILURE">Failure</option>
            <option value="PARTIAL_FAILURE">Partial Failure</option>
          </select>

          {(actionFilter || actorEmail || targetTypeFilter || outcomeFilter) && (
            <button
              onClick={() => {
                setActionFilter('')
                setActorEmail('')
                setTargetTypeFilter('')
                setOutcomeFilter('')
                setOffset(0)
              }}
              className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-medium px-2 py-1"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-800/60 border-b border-gray-200 dark:border-gray-800 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4">Actor</th>
                <th className="py-3.5 px-4">Action</th>
                <th className="py-3.5 px-4">Target</th>
                <th className="py-3.5 px-4">Outcome</th>
                <th className="py-3.5 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800 text-sm">
              {isLoading ? (
                <tr>
                  <td colSpan="6" className="text-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent mx-auto mb-2"></div>
                    <span className="text-gray-500 dark:text-gray-400 text-xs">Loading audit logs...</span>
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan="6" className="text-center py-12 text-gray-500 dark:text-gray-400">
                    <ClipboardList className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
                    <p className="font-medium">No audit events recorded</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Actions such as role changes and deletions will appear here.</p>
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50/80 dark:hover:bg-gray-800/50 transition-colors">
                    <td className="py-3.5 px-4 text-xs text-gray-500 dark:text-gray-400 font-mono">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}
                    </td>
                    <td className="py-3.5 px-4">
                      <div>
                        <div className="font-medium text-gray-900 dark:text-white text-xs">{log.actor_email || 'System'}</div>
                        <span className="text-[10px] text-gray-500 dark:text-gray-400 capitalize">{log.actor_role || 'System'}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      {getActionBadge(log.action)}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="text-xs font-mono text-gray-700 dark:text-gray-300">
                        <span className="text-gray-400 dark:text-gray-500">{log.target_type ? `${log.target_type}: ` : ''}</span>
                        <span>{log.target_id || 'N/A'}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      {getOutcomeBadge(log.outcome)}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {log.details ? (
                        <button
                          onClick={() => setActiveDetailLog(log)}
                          className="px-2.5 py-1 text-xs border border-gray-300 dark:border-gray-700 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 font-medium inline-flex items-center gap-1 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>View</span>
                        </button>
                      ) : (
                        <span className="text-xs text-gray-400 dark:text-gray-500">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500 dark:text-gray-400">
          <div>
            Showing <span className="font-semibold text-gray-700 dark:text-gray-200">{logs.length > 0 ? offset + 1 : 0}</span> to{' '}
            <span className="font-semibold text-gray-700 dark:text-gray-200">{Math.min(offset + limit, total)}</span> of{' '}
            <span className="font-semibold text-gray-700 dark:text-gray-200">{total}</span> events
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setOffset(o => Math.max(o - limit, 0))}
              disabled={offset <= 0 || isLoading}
              className="p-1.5 border border-gray-300 dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-medium">Page {currentPage} of {totalPages}</span>
            <button
              onClick={() => setOffset(o => o + limit)}
              disabled={offset + limit >= total || isLoading}
              className="p-1.5 border border-gray-300 dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Details Modal */}
      {activeDetailLog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4 border border-gray-200 dark:border-gray-800">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <span>Audit Event Payload</span>
              </h3>
              <button
                onClick={() => setActiveDetailLog(null)}
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded-lg border border-gray-200 dark:border-gray-700 text-xs space-y-1 font-mono">
              <div><span className="text-gray-500 dark:text-gray-400">Action:</span> <span className="font-semibold text-gray-900 dark:text-gray-100">{activeDetailLog.action}</span></div>
              <div><span className="text-gray-500 dark:text-gray-400">Actor:</span> <span className="text-gray-900 dark:text-gray-100">{activeDetailLog.actor_email} ({activeDetailLog.actor_role})</span></div>
              <div><span className="text-gray-500 dark:text-gray-400">Timestamp:</span> <span className="text-gray-900 dark:text-gray-100">{activeDetailLog.created_at}</span></div>
              <div><span className="text-gray-500 dark:text-gray-400">Outcome:</span> <span className="text-gray-900 dark:text-gray-100">{activeDetailLog.outcome}</span></div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Metadata / Details</label>
              <pre className="bg-gray-900 text-emerald-400 p-4 rounded-xl text-xs overflow-x-auto max-h-60 font-mono border border-gray-800">
                {JSON.stringify(activeDetailLog.details, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setActiveDetailLog(null)}
                className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AuditLogs
