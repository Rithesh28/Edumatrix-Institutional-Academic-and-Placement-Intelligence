import React, { useState, useEffect, useRef } from 'react'
import { useAuthStore } from '../../store/authStore'
import { studyBuddyAPI } from '../../services/api'
import toast from 'react-hot-toast'

const StudyBuddy = () => {
  const { user } = useAuthStore()
  const [subjects, setSubjects] = useState([])
  const [selectedSubjectId, setSelectedSubjectId] = useState('')
  const [messages, setMessages] = useState([])
  const [inputQuestion, setInputQuestion] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [loadingSubjects, setLoadingSubjects] = useState(true)
  const [expandedCitations, setExpandedCitations] = useState({})
  const messagesEndRef = useRef(null)

  // Quick prompt suggestions
  const samplePrompts = [
    'What are the core units covered in this syllabus?',
    'Explain the fundamental concepts in Unit 1.',
    'What topics should I prepare for our upcoming assessments?',
    'Summarize the prerequisites and learning objectives.'
  ]

  useEffect(() => {
    fetchSubjects()
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const fetchSubjects = async () => {
    try {
      setLoadingSubjects(true)
      const res = await studyBuddyAPI.getSubjects()
      const data = res.data || []
      setSubjects(data)
    } catch (err) {
      console.error('Failed to load syllabus subjects:', err)
      toast.error('Could not load subjects for your department.')
    } finally {
      setLoadingSubjects(false)
    }
  }

  const handleSend = async (questionText = inputQuestion) => {
    const text = (questionText || '').trim()
    if (!text || isLoading) return

    const studentMessage = {
      id: Date.now(),
      sender: 'student',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      subjectId: selectedSubjectId ? Number(selectedSubjectId) : null
    }

    setMessages((prev) => [...prev, studentMessage])
    setInputQuestion('')
    setIsLoading(true)

    try {
      const subjectFilter = selectedSubjectId ? Number(selectedSubjectId) : null
      const res = await studyBuddyAPI.askQuestion(text, subjectFilter)
      const data = res.data

      const aiMessage = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: data.answer,
        hasSufficientEvidence: data.has_sufficient_evidence,
        citations: data.citations || [],
        modelUsed: data.model_used,
        latencyMs: data.latency_ms,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }

      setMessages((prev) => [...prev, aiMessage])
    } catch (err) {
      console.error('Study Buddy query error:', err)
      const errorMessage = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: 'Sorry, I encountered a temporary problem retrieving the syllabus material. Please check your connection and try again.',
        hasSufficientEvidence: false,
        isError: true,
        citations: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      setMessages((prev) => [...prev, errorMessage])
      toast.error(err.response?.data?.detail || 'Failed to get answer from Study Buddy.')
    } finally {
      setIsLoading(false)
    }
  }

  const toggleCitation = (msgId, citIndex) => {
    const key = `${msgId}-${citIndex}`
    setExpandedCitations((prev) => ({
      ...prev,
      [key]: !prev[key]
    }))
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClearChat = () => {
    if (messages.length === 0) return
    if (window.confirm('Clear your current Study Buddy conversation?')) {
      setMessages([])
    }
  }

  const activeSubjectName = subjects.find(
    (s) => String(s.id) === String(selectedSubjectId)
  )?.name

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] max-w-6xl mx-auto">
      {/* Top Header & Filters */}
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 mb-4 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 transition-colors">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">📚</span>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">
              Study Buddy
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-300">
              RAG Academic Assistant
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Grounded answers strictly referencing approved syllabus documents for{' '}
            <span className="font-semibold text-gray-700 dark:text-gray-300">
              {user?.department || 'your department'}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          {/* Subject Filter Dropdown */}
          <div className="relative flex-1 sm:w-64">
            <select
              value={selectedSubjectId}
              onChange={(e) => setSelectedSubjectId(e.target.value)}
              className="w-full text-sm bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              disabled={loadingSubjects}
            >
              <option value="">All Department Subjects</option>
              {subjects.map((sub) => (
                <option key={sub.id} value={sub.id}>
                  {sub.code} - {sub.name}
                </option>
              ))}
            </select>
          </div>

          {messages.length > 0 && (
            <button
              onClick={handleClearChat}
              title="Clear conversation"
              className="px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Chat Messages Feed */}
      <div className="flex-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl shadow-sm p-4 sm:p-6 overflow-y-auto space-y-5 transition-colors">
        {messages.length === 0 ? (
          /* Empty State Hero */
          <div className="h-full flex flex-col justify-center items-center text-center px-4 py-8">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-3xl text-white shadow-lg shadow-blue-500/20 mb-4">
              🎓
            </div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Welcome to your Academic Study Buddy
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mt-1 mb-6">
              Ask questions about course syllabus topics, unit objectives, and academic material. Answers are verified and cited directly from official syllabus documents.
            </p>

            {activeSubjectName && (
              <div className="mb-4 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-900">
                <span>Filtering by:</span>
                <span className="font-bold">{activeSubjectName}</span>
              </div>
            )}

            {/* Prompt Suggestion Chips */}
            <div className="w-full max-w-xl grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
              {samplePrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(prompt)}
                  className="p-3 text-xs bg-gray-50 dark:bg-gray-800/70 hover:bg-blue-50 dark:hover:bg-blue-900/30 border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 rounded-xl text-gray-700 dark:text-gray-300 transition-all text-left flex items-start gap-2 group"
                >
                  <span className="text-blue-500 group-hover:translate-x-0.5 transition-transform">
                    💡
                  </span>
                  <span>{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message List */
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.sender === 'student' ? 'items-end' : 'items-start'
              }`}
            >
              <div
                className={`max-w-2xl sm:max-w-3xl rounded-2xl p-4 shadow-sm ${
                  msg.sender === 'student'
                    ? 'bg-blue-600 text-white rounded-br-none'
                    : 'bg-gray-50 dark:bg-gray-800/90 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 rounded-bl-none'
                }`}
              >
                {/* Header for assistant */}
                {msg.sender === 'assistant' && (
                  <div className="flex items-center justify-between pb-2 mb-2 border-b border-gray-200/60 dark:border-gray-700/60 text-xs">
                    <div className="flex items-center gap-1.5 font-semibold text-blue-600 dark:text-blue-400">
                      <span>🤖</span>
                      <span>Study Buddy</span>
                      {msg.modelUsed && (
                        <span className="ml-1 text-[10px] text-gray-400 dark:text-gray-500 font-normal">
                          ({msg.modelUsed.includes('Qwen') ? 'Qwen Instruct' : 'Synthesized'})
                        </span>
                      )}
                    </div>
                    {msg.latencyMs && (
                      <span className="text-[10px] text-gray-400">
                        {Math.round(msg.latencyMs)}ms
                      </span>
                    )}
                  </div>
                )}

                {/* Insufficient Evidence Warning Banner */}
                {msg.sender === 'assistant' && !msg.hasSufficientEvidence && !msg.isError && (
                  <div className="mb-3 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-xs flex items-center gap-2">
                    <span className="text-base">⚠️</span>
                    <span>
                      <strong>Notice:</strong> This query is not covered in the approved syllabus material.
                    </span>
                  </div>
                )}

                {/* Main Message Body */}
                <div className="text-sm whitespace-pre-wrap leading-relaxed">
                  {msg.text}
                </div>

                {/* Verified Source Citations Section */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                      <span>📑</span>
                      <span>Verified Syllabus Sources ({msg.citations.length}):</span>
                    </div>

                    <div className="space-y-2">
                      {msg.citations.map((cit, cIdx) => {
                        const isExpanded = !!expandedCitations[`${msg.id}-${cIdx}`]
                        return (
                          <div
                            key={cIdx}
                            className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-750 rounded-lg p-2.5 text-xs transition-colors"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-1">
                              <div className="font-semibold text-blue-600 dark:text-blue-400">
                                {cit.subject_code} - {cit.subject_name}
                              </div>
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                                {Math.round(cit.relevance_score * 100)}% match
                              </span>
                            </div>

                            <div className="text-gray-600 dark:text-gray-400 mt-1 flex flex-wrap gap-x-3 gap-y-1">
                              {cit.unit_number && (
                                <span>
                                  <strong>Unit {cit.unit_number}:</strong> {cit.unit_title || 'Unit'}
                                </span>
                              )}
                              {cit.topic_title && (
                                <span>
                                  <strong>Topic:</strong> {cit.topic_title}
                                </span>
                              )}
                              {cit.source_page && (
                                <span>
                                  <strong>Page:</strong> {cit.source_page}
                                </span>
                              )}
                            </div>

                            {/* Source evidence snippet toggle */}
                            {cit.source_evidence && (
                              <div className="mt-1.5 pt-1.5 border-t border-gray-100 dark:border-gray-800">
                                <button
                                  onClick={() => toggleCitation(msg.id, cIdx)}
                                  className="text-[11px] text-blue-500 hover:text-blue-600 font-medium flex items-center gap-1"
                                >
                                  <span>{isExpanded ? 'Hide passage snippet' : 'View passage snippet'}</span>
                                  <span>{isExpanded ? '▲' : '▼'}</span>
                                </button>
                                {isExpanded && (
                                  <div className="mt-1.5 p-2 bg-gray-50 dark:bg-gray-800/60 rounded text-[11px] text-gray-700 dark:text-gray-300 font-mono italic">
                                    "{cit.source_evidence}"
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Timestamp */}
                <div
                  className={`text-[10px] mt-2 text-right ${
                    msg.sender === 'student'
                      ? 'text-blue-100'
                      : 'text-gray-400 dark:text-gray-500'
                  }`}
                >
                  {msg.timestamp}
                </div>
              </div>
            </div>
          ))
        )}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex flex-col items-start space-y-1">
            <div className="bg-gray-50 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 rounded-2xl rounded-bl-none p-4 max-w-md shadow-sm">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 mb-2">
                <span className="animate-spin text-sm">⚙️</span>
                <span>Searching approved syllabus material...</span>
              </div>
              <div className="flex space-x-1.5 py-1">
                <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce"></div>
              </div>
              <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-2">
                Retrieving verified syllabus chunks & generating grounded response...
              </p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="mt-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-2.5 shadow-sm transition-colors">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              selectedSubjectId
                ? `Ask anything about ${activeSubjectName || 'this subject'}...`
                : 'Ask an academic question about your course syllabus...'
            }
            className="flex-1 text-sm bg-transparent border-0 px-3 py-2 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-0"
            disabled={isLoading}
          />

          <button
            onClick={() => handleSend()}
            disabled={isLoading || !inputQuestion.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-800 text-white rounded-lg text-sm font-semibold transition-all flex items-center gap-1.5 shadow-sm disabled:cursor-not-allowed cursor-pointer"
          >
            <span>Ask</span>
            <svg
              className="w-4 h-4 transform rotate-90"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

export default StudyBuddy
