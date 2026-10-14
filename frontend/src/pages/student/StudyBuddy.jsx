import React, { useState, useEffect, useRef } from 'react'
import { useAuthStore } from '../../store/authStore'
import { studyBuddyAPI } from '../../services/api'
import toast from 'react-hot-toast'

const StudyBuddy = () => {
  const { user } = useAuthStore()

  // Navigation tab state: 'chat' | 'summaries' | 'quizzes'
  const [activeTab, setActiveTab] = useState('chat')

  // Common Subject & Syllabus units/topics state
  const [subjects, setSubjects] = useState([])
  const [loadingSubjects, setLoadingSubjects] = useState(true)
  const [selectedSubjectId, setSelectedSubjectId] = useState('')
  const [subjectDetails, setSubjectDetails] = useState(null)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [selectedUnitId, setSelectedUnitId] = useState('')
  const [selectedTopicId, setSelectedTopicId] = useState('')

  // ----------------------------------------------------
  // CHAT STATE
  // ----------------------------------------------------
  const [messages, setMessages] = useState([])
  const [inputQuestion, setInputQuestion] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [expandedChatCitations, setExpandedChatCitations] = useState({})
  const messagesEndRef = useRef(null)

  const samplePrompts = [
    'What are the core units covered in this syllabus?',
    'Explain the fundamental concepts in Unit 1.',
    'What topics should I prepare for our upcoming assessments?',
    'Summarize the prerequisites and learning objectives.'
  ]

  // ----------------------------------------------------
  // SUMMARIES STATE
  // ----------------------------------------------------
  const [summaryFormat, setSummaryFormat] = useState('concise') // 'concise' | 'detailed'
  const [isSummaryLoading, setIsSummaryLoading] = useState(false)
  const [summaryResult, setSummaryResult] = useState(null)
  const [expandedSummaryCitations, setExpandedSummaryCitations] = useState({})

  // ----------------------------------------------------
  // QUIZZES STATE
  // ----------------------------------------------------
  const [quizNumQuestions, setQuizNumQuestions] = useState(5)
  const [quizDifficulty, setQuizDifficulty] = useState('medium')
  const [isQuizGenerating, setIsQuizGenerating] = useState(false)
  const [activeQuiz, setActiveQuiz] = useState(null) // public quiz attempt
  const [studentAnswers, setStudentAnswers] = useState({}) // { [question_id]: option_idx }
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [isSubmittingQuiz, setIsSubmittingQuiz] = useState(false)
  const [quizResult, setQuizResult] = useState(null)
  const [pastAttempts, setPastAttempts] = useState([])
  const [loadingPastAttempts, setLoadingPastAttempts] = useState(false)
  const [showPastAttempts, setShowPastAttempts] = useState(false)
  const [expandedQuizCitations, setExpandedQuizCitations] = useState({})

  // Initial load
  useEffect(() => {
    fetchSubjects()
  }, [])

  // Auto-scroll chat
  useEffect(() => {
    if (activeTab === 'chat') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isChatLoading, activeTab])

  // Load syllabus units and topics when subject changes
  useEffect(() => {
    if (!selectedSubjectId) {
      setSubjectDetails(null)
      setSelectedUnitId('')
      setSelectedTopicId('')
      return
    }

    const sub = subjects.find((s) => String(s.id) === String(selectedSubjectId))
    if (sub && sub.published_document_id) {
      fetchSyllabusDetail(sub.published_document_id)
    } else {
      setSubjectDetails(null)
      setSelectedUnitId('')
      setSelectedTopicId('')
    }
  }, [selectedSubjectId, subjects])

  // Load past quiz attempts when switching to quiz tab
  useEffect(() => {
    if (activeTab === 'quizzes') {
      fetchPastAttempts()
    }
  }, [activeTab, selectedSubjectId])

  // Reset topic when unit changes
  const handleUnitChange = (unitId) => {
    setSelectedUnitId(unitId)
    setSelectedTopicId('')
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

  const fetchSyllabusDetail = async (docId) => {
    try {
      setLoadingDetails(true)
      const res = await studyBuddyAPI.getSyllabusDetail(docId)
      setSubjectDetails(res.data)
    } catch (err) {
      console.error('Failed to load syllabus unit details:', err)
      setSubjectDetails(null)
    } finally {
      setLoadingDetails(false)
    }
  }

  const fetchPastAttempts = async () => {
    try {
      setLoadingPastAttempts(true)
      const res = await studyBuddyAPI.getQuizAttempts(selectedSubjectId ? Number(selectedSubjectId) : null)
      setPastAttempts(res.data || [])
    } catch (err) {
      console.error('Failed to load past quiz attempts:', err)
    } finally {
      setLoadingPastAttempts(false)
    }
  }

  // ----------------------------------------------------
  // CHAT HANDLERS
  // ----------------------------------------------------
  const handleSendChat = async (questionText = inputQuestion) => {
    const text = (questionText || '').trim()
    if (!text || isChatLoading) return

    const studentMessage = {
      id: Date.now(),
      sender: 'student',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      subjectId: selectedSubjectId ? Number(selectedSubjectId) : null
    }

    setMessages((prev) => [...prev, studentMessage])
    setInputQuestion('')
    setIsChatLoading(true)

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
      setIsChatLoading(false)
    }
  }

  const handleClearChat = () => {
    if (messages.length === 0) return
    if (window.confirm('Clear your current Study Buddy conversation?')) {
      setMessages([])
    }
  }

  // ----------------------------------------------------
  // SUMMARY HANDLERS
  // ----------------------------------------------------
  const handleGenerateSummary = async () => {
    if (!selectedSubjectId) {
      toast.error('Please select an active academic subject first.')
      return
    }

    setIsSummaryLoading(true)
    setSummaryResult(null)
    setExpandedSummaryCitations({})

    try {
      const payload = {
        subject_id: Number(selectedSubjectId),
        unit_id: selectedUnitId ? Number(selectedUnitId) : null,
        topic_id: selectedTopicId ? Number(selectedTopicId) : null,
        format_type: summaryFormat
      }

      const res = await studyBuddyAPI.generateSummary(payload)
      setSummaryResult(res.data)
      if (res.data.has_sufficient_evidence) {
        toast.success('Study summary generated successfully!')
      } else {
        toast('Insufficient syllabus material for full summary.', { icon: '⚠️' })
      }
    } catch (err) {
      console.error('Summary generation error:', err)
      toast.error(err.response?.data?.detail || 'Failed to generate study summary.')
    } finally {
      setIsSummaryLoading(false)
    }
  }

  const handleCopySummary = () => {
    if (!summaryResult?.summary) return
    navigator.clipboard.writeText(summaryResult.summary)
    toast.success('Summary copied to clipboard!')
  }

  // ----------------------------------------------------
  // QUIZ HANDLERS
  // ----------------------------------------------------
  const handleGenerateQuiz = async () => {
    if (!selectedSubjectId) {
      toast.error('Please select an active academic subject first.')
      return
    }

    setIsQuizGenerating(true)
    setActiveQuiz(null)
    setQuizResult(null)
    setStudentAnswers({})
    setCurrentQuestionIndex(0)
    setExpandedQuizCitations({})

    try {
      const payload = {
        subject_id: Number(selectedSubjectId),
        unit_id: selectedUnitId ? Number(selectedUnitId) : null,
        topic_id: selectedTopicId ? Number(selectedTopicId) : null,
        num_questions: Number(quizNumQuestions),
        difficulty: quizDifficulty
      }

      const res = await studyBuddyAPI.generateQuiz(payload)
      setActiveQuiz(res.data)
      setShowPastAttempts(false)
      if (res.data.shortfall_note) {
        toast(res.data.shortfall_note, { icon: 'ℹ️' })
      } else {
        toast.success(`Generated ${res.data.total_questions} syllabus-grounded questions!`)
      }
    } catch (err) {
      console.error('Quiz generation error:', err)
      toast.error(err.response?.data?.detail || 'Failed to generate quiz from syllabus.')
    } finally {
      setIsQuizGenerating(false)
    }
  }

  const handleSelectOption = (questionId, optionIndex) => {
    setStudentAnswers((prev) => ({
      ...prev,
      [String(questionId)]: optionIndex
    }))
  }

  const handleSubmitQuiz = async () => {
    if (!activeQuiz) return

    const totalQ = activeQuiz.questions.length
    const answeredQ = Object.keys(studentAnswers).length

    if (answeredQ < totalQ) {
      const confirmIncomplete = window.confirm(
        `You have answered ${answeredQ} of ${totalQ} questions. Are you sure you want to submit?`
      )
      if (!confirmIncomplete) return
    }

    setIsSubmittingQuiz(true)
    try {
      const res = await studyBuddyAPI.submitQuiz(activeQuiz.id, studentAnswers)
      setQuizResult(res.data)
      setActiveQuiz(null)
      toast.success(`Quiz completed! Score: ${res.data.score}/${res.data.max_score} (${res.data.percentage}%)`)
      fetchPastAttempts()
    } catch (err) {
      console.error('Quiz submission error:', err)
      toast.error(err.response?.data?.detail || 'Failed to submit quiz.')
    } finally {
      setIsSubmittingQuiz(false)
    }
  }

  const handleViewPastAttempt = async (attemptId) => {
    try {
      const res = await studyBuddyAPI.getQuizResult(attemptId)
      setQuizResult(res.data)
      setActiveQuiz(null)
      setShowPastAttempts(false)
    } catch (err) {
      console.error('Failed to load attempt details:', err)
      toast.error(err.response?.data?.detail || 'Could not load quiz result.')
    }
  }

  // Filter available topics based on selected unit
  const activeUnit = subjectDetails?.units?.find((u) => String(u.id) === String(selectedUnitId))
  const availableTopics = activeUnit?.topics || []

  return (
    <div className="flex flex-col min-h-[calc(100vh-120px)] max-w-6xl mx-auto">
      {/* ========================================================
          TOP HEADER & MAIN TAB NAVIGATION
      ======================================================== */}
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 mb-4 shadow-sm transition-colors">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-2xl">📚</span>
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                Study Buddy
              </h1>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-300">
                Institutional Academic Assistant
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Approved syllabus-grounded chat, revision summaries, and quizzes for{' '}
              <span className="font-semibold text-gray-700 dark:text-gray-300">
                {user?.department || 'your department'}
              </span>
            </p>
          </div>

          {/* Tab Switcher Pills */}
          <div className="flex items-center bg-gray-100 dark:bg-gray-800 p-1 rounded-lg border border-gray-200 dark:border-gray-700 w-full sm:w-auto">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === 'chat'
                  ? 'bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <span>💬</span>
              <span>Ask Buddy</span>
            </button>
            <button
              onClick={() => setActiveTab('summaries')}
              className={`flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === 'summaries'
                  ? 'bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <span>📝</span>
              <span>Study Summaries</span>
            </button>
            <button
              onClick={() => setActiveTab('quizzes')}
              className={`flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === 'quizzes'
                  ? 'bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <span>🎯</span>
              <span>Practice Quizzes</span>
            </button>
          </div>
        </div>

        {/* Global Subject & Unit Filter Row (Visible across all tabs) */}
        <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-800 grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Subject Dropdown */}
          <div>
            <label className="block text-[11px] font-medium text-gray-500 dark:text-gray-400 mb-1">
              Select Subject {activeTab !== 'chat' && <span className="text-red-500">*</span>}
            </label>
            <select
              value={selectedSubjectId}
              onChange={(e) => setSelectedSubjectId(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-lg px-2.5 py-1.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              disabled={loadingSubjects}
            >
              <option value="">{activeTab === 'chat' ? 'All Department Subjects' : '-- Select Subject --'}</option>
              {subjects.map((sub) => (
                <option key={sub.id} value={sub.id}>
                  {sub.code} - {sub.name}
                </option>
              ))}
            </select>
          </div>

          {/* Unit Dropdown */}
          <div>
            <label className="block text-[11px] font-medium text-gray-500 dark:text-gray-400 mb-1">
              Syllabus Unit (Optional)
            </label>
            <select
              value={selectedUnitId}
              onChange={(e) => handleUnitChange(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-lg px-2.5 py-1.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              disabled={!subjectDetails || !subjectDetails.units?.length || loadingDetails}
            >
              <option value="">All Units in Syllabus</option>
              {subjectDetails?.units?.map((u) => (
                <option key={u.id} value={u.id}>
                  Unit {u.unit_number || u.order}: {u.title}
                </option>
              ))}
            </select>
          </div>

          {/* Topic Dropdown */}
          <div>
            <label className="block text-[11px] font-medium text-gray-500 dark:text-gray-400 mb-1">
              Topic (Optional)
            </label>
            <select
              value={selectedTopicId}
              onChange={(e) => setSelectedTopicId(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-lg px-2.5 py-1.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              disabled={!selectedUnitId || !availableTopics.length}
            >
              <option value="">All Topics in Unit</option>
              {availableTopics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* ========================================================
          TAB 1: RAG CHAT
      ======================================================== */}
      {activeTab === 'chat' && (
        <div className="flex flex-col flex-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm transition-colors">
          {/* Messages Feed */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 max-h-[calc(100vh-320px)]">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-12 text-center">
                <div className="w-16 h-16 rounded-full bg-blue-50 dark:bg-blue-950/40 flex items-center justify-center text-3xl mb-3">
                  🎓
                </div>
                <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200 mb-1">
                  How can I help you study today?
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 max-w-md mb-6">
                  Ask questions about course definitions, unit syllabus topics, learning objectives, or exam expectations.
                </p>

                <div className="w-full max-w-lg grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                  {samplePrompts.map((prompt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendChat(prompt)}
                      className="p-3 text-xs bg-gray-50 dark:bg-gray-800 hover:bg-blue-50 dark:hover:bg-blue-950/40 border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700 text-gray-700 dark:text-gray-300 rounded-lg text-left transition-all"
                    >
                      💡 {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.sender === 'student' ? 'items-end' : 'items-start'}`}
                >
                  <div
                    className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 shadow-sm transition-colors ${
                      msg.sender === 'student'
                        ? 'bg-blue-600 text-white rounded-br-sm'
                        : msg.isError
                        ? 'bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-900 dark:text-red-200 rounded-bl-sm'
                        : 'bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-sm'
                    }`}
                  >
                    {msg.sender === 'assistant' && (
                      <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-gray-200/60 dark:border-gray-700">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-600 dark:text-blue-400">
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

                    {msg.sender === 'assistant' && !msg.hasSufficientEvidence && !msg.isError && (
                      <div className="mb-3 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-xs flex items-center gap-2">
                        <span className="text-base">⚠️</span>
                        <span>
                          <strong>Notice:</strong> This query is not covered in the approved syllabus material.
                        </span>
                      </div>
                    )}

                    <div className="text-sm whitespace-pre-wrap leading-relaxed">
                      {msg.text}
                    </div>

                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                          <span>📑</span>
                          <span>Verified Syllabus Sources ({msg.citations.length}):</span>
                        </div>

                        <div className="space-y-2">
                          {msg.citations.map((cit, cIdx) => {
                            const isExpanded = !!expandedChatCitations[`${msg.id}-${cIdx}`]
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

                                {cit.source_evidence && (
                                  <div className="mt-1.5 pt-1.5 border-t border-gray-100 dark:border-gray-800">
                                    <button
                                      onClick={() => {
                                        const key = `${msg.id}-${cIdx}`
                                        setExpandedChatCitations((p) => ({ ...p, [key]: !p[key] }))
                                      }}
                                      className="text-[11px] text-blue-500 hover:text-blue-600 font-medium flex items-center gap-1"
                                    >
                                      <span>{isExpanded ? 'Hide passage snippet' : 'View passage snippet'}</span>
                                      <span>{isExpanded ? '▲' : '▼'}</span>
                                    </button>
                                    {isExpanded && (
                                      <p className="mt-1.5 text-xs text-gray-700 dark:text-gray-300 italic bg-gray-50 dark:bg-gray-800/80 p-2 rounded border border-gray-200 dark:border-gray-700 whitespace-pre-wrap">
                                        "{cit.source_evidence}"
                                      </p>
                                    )}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                  <span className="text-[10px] text-gray-400 mt-1 px-1">
                    {msg.timestamp}
                  </span>
                </div>
              ))
            )}

            {isChatLoading && (
              <div className="flex items-start gap-3">
                <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-4 shadow-sm rounded-bl-sm">
                  <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse delay-75" />
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse delay-150" />
                    <span className="ml-1 text-xs font-medium">Retrieving syllabus evidence & synthesizing answer...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input Bar */}
          <div className="p-3 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={inputQuestion}
                onChange={(e) => setInputQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendChat()
                  }
                }}
                placeholder={
                  selectedSubjectId
                    ? "Ask a question about this subject's syllabus..."
                    : "Ask about any syllabus topic in your department..."
                }
                disabled={isChatLoading}
                className="flex-1 text-sm bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              />
              <button
                onClick={() => handleSendChat()}
                disabled={!inputQuestion.trim() || isChatLoading}
                className="px-5 py-3 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl shadow-sm transition-all flex items-center gap-1.5"
              >
                <span>Send</span>
                <span>➤</span>
              </button>
              {messages.length > 0 && (
                <button
                  onClick={handleClearChat}
                  title="Clear conversation"
                  className="px-3 py-3 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-xl transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================
          TAB 2: STUDY SUMMARIES
      ======================================================== */}
      {activeTab === 'summaries' && (
        <div className="space-y-4">
          {/* Controls Card */}
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm transition-colors">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div>
                <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <span>📝</span>
                  <span>Syllabus Summary Generator</span>
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Produce grounded revision notes or detailed conceptual breakdowns from approved course syllabi.
                </p>
              </div>

              {/* Format Toggle & Action */}
              <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
                <div className="flex items-center bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg border border-gray-200 dark:border-gray-700 text-xs">
                  <button
                    onClick={() => setSummaryFormat('concise')}
                    className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                      summaryFormat === 'concise'
                        ? 'bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm'
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'
                    }`}
                  >
                    ⚡ Concise Notes
                  </button>
                  <button
                    onClick={() => setSummaryFormat('detailed')}
                    className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                      summaryFormat === 'detailed'
                        ? 'bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm'
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'
                    }`}
                  >
                    📖 Detailed Breakdown
                  </button>
                </div>

                <button
                  onClick={handleGenerateSummary}
                  disabled={!selectedSubjectId || isSummaryLoading}
                  className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-sm transition-all flex items-center gap-1.5"
                >
                  {isSummaryLoading ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Synthesizing...</span>
                    </>
                  ) : (
                    <>
                      <span>✨</span>
                      <span>Generate Summary</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Results Area */}
          {summaryResult ? (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm transition-colors">
              {/* Header */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-4 mb-4 border-b border-gray-200 dark:border-gray-800 gap-2">
                <div>
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                    {summaryResult.title}
                  </h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400">
                      Format: {summaryResult.format_type === 'concise' ? 'Concise Revision Notes' : 'Detailed Explanation'}
                    </span>
                    <span className="text-gray-300 dark:text-gray-700">•</span>
                    <span className="text-[11px] text-gray-500 dark:text-gray-400">
                      Engine: {summaryResult.model_used.includes('Qwen') ? 'Qwen Instruct' : 'Deterministic Synthesizer'}
                    </span>
                    {summaryResult.latency_ms && (
                      <>
                        <span className="text-gray-300 dark:text-gray-700">•</span>
                        <span className="text-[11px] text-gray-400">
                          {Math.round(summaryResult.latency_ms)}ms
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <button
                  onClick={handleCopySummary}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <span>📋</span>
                  <span>Copy Notes</span>
                </button>
              </div>

              {/* Insufficient Evidence Warning Banner */}
              {!summaryResult.has_sufficient_evidence && (
                <div className="mb-4 px-3 py-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-xs flex items-center gap-2">
                  <span className="text-base">⚠️</span>
                  <span>
                    <strong>Notice:</strong> The approved syllabus does not contain sufficient verified passages for this selection.
                  </span>
                </div>
              )}

              {/* Summary Text Content */}
              <div className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap leading-relaxed space-y-2">
                {summaryResult.summary}
              </div>

              {/* Verified Citations */}
              {summaryResult.citations && summaryResult.citations.length > 0 && (
                <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-800">
                  <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-1.5">
                    <span>📑</span>
                    <span>Verified Syllabus Sources ({summaryResult.citations.length})</span>
                  </h4>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {summaryResult.citations.map((cit, cIdx) => {
                      const isExpanded = !!expandedSummaryCitations[cIdx]
                      return (
                        <div
                          key={cIdx}
                          className="bg-gray-50 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-xs"
                        >
                          <div className="font-semibold text-blue-600 dark:text-blue-400">
                            {cit.subject_code} - {cit.subject_name} (v{cit.version})
                          </div>
                          <div className="text-gray-600 dark:text-gray-400 mt-1 space-y-0.5">
                            {cit.unit_number && (
                              <p><strong>Unit {cit.unit_number}:</strong> {cit.unit_title || 'Unit'}</p>
                            )}
                            {cit.topic_title && (
                              <p><strong>Topic:</strong> {cit.topic_title}</p>
                            )}
                            {cit.source_page && (
                              <p><strong>Page:</strong> {cit.source_page}</p>
                            )}
                          </div>

                          {cit.source_evidence && (
                            <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                              <button
                                onClick={() =>
                                  setExpandedSummaryCitations((p) => ({ ...p, [cIdx]: !p[cIdx] }))
                                }
                                className="text-[11px] text-blue-500 hover:text-blue-600 font-medium flex items-center gap-1"
                              >
                                <span>{isExpanded ? 'Hide passage snippet' : 'View passage snippet'}</span>
                                <span>{isExpanded ? '▲' : '▼'}</span>
                              </button>
                              {isExpanded && (
                                <p className="mt-1.5 text-xs text-gray-700 dark:text-gray-300 italic bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700 whitespace-pre-wrap">
                                  "{cit.source_evidence}"
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-12 text-center shadow-sm transition-colors">
              <span className="text-4xl mb-3 block">📖</span>
              <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">
                Select a subject above and click Generate Summary
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                Study Buddy will synthesize clean revision notes based strictly on the approved syllabus.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ========================================================
          TAB 3: PRACTICE QUIZZES
      ======================================================== */}
      {activeTab === 'quizzes' && (
        <div className="space-y-4">
          {/* Controls Bar & Mode Toggle */}
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm transition-colors">
            <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
              <div>
                <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <span>🎯</span>
                  <span>Syllabus-Grounded Practice Quizzes</span>
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Test your mastery with multiple-choice questions grounded in approved institutional syllabus passages.
                </p>
              </div>

              {/* Controls */}
              <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto">
                {/* Number of Questions */}
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-gray-500 dark:text-gray-400">Questions:</span>
                  <select
                    value={quizNumQuestions}
                    onChange={(e) => setQuizNumQuestions(Number(e.target.value))}
                    className="text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-lg px-2 py-1.5"
                    disabled={isQuizGenerating || activeQuiz}
                  >
                    <option value={3}>3 Questions</option>
                    <option value={5}>5 Questions</option>
                    <option value={8}>8 Questions</option>
                    <option value={10}>10 Questions</option>
                  </select>
                </div>

                {/* Difficulty */}
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-gray-500 dark:text-gray-400">Difficulty:</span>
                  <select
                    value={quizDifficulty}
                    onChange={(e) => setQuizDifficulty(e.target.value)}
                    className="text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-lg px-2 py-1.5"
                    disabled={isQuizGenerating || activeQuiz}
                  >
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                  </select>
                </div>

                {/* Action Buttons */}
                {!activeQuiz ? (
                  <button
                    onClick={handleGenerateQuiz}
                    disabled={!selectedSubjectId || isQuizGenerating}
                    className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-sm transition-all flex items-center gap-1.5"
                  >
                    {isQuizGenerating ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span>Generating Quiz...</span>
                      </>
                    ) : (
                      <>
                        <span>🚀</span>
                        <span>Start New Quiz</span>
                      </>
                    )}
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      if (window.confirm('Cancel current quiz attempt? Progress will be lost.')) {
                        setActiveQuiz(null)
                        setStudentAnswers({})
                      }
                    }}
                    className="px-3 py-2 text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 hover:bg-red-100 rounded-lg transition-colors"
                  >
                    Cancel Quiz
                  </button>
                )}

                <button
                  onClick={() => setShowPastAttempts((p) => !p)}
                  className="px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  📜 {showPastAttempts ? 'Hide History' : 'Past Attempts'} ({pastAttempts.length})
                </button>
              </div>
            </div>
          </div>

          {/* Past Attempts Drawer / Card */}
          {showPastAttempts && (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm transition-colors">
              <h3 className="text-sm font-bold text-gray-900 dark:text-white mb-3 flex items-center gap-1.5">
                <span>📜</span>
                <span>Past Quiz Attempts</span>
              </h3>

              {pastAttempts.length === 0 ? (
                <p className="text-xs text-gray-500 dark:text-gray-400 py-3 text-center">
                  No completed quiz attempts found for this selection.
                </p>
              ) : (
                <div className="divide-y divide-gray-100 dark:divide-gray-800">
                  {pastAttempts.map((att) => (
                    <div
                      key={att.id}
                      className="py-2.5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2"
                    >
                      <div>
                        <div className="font-semibold text-xs text-gray-900 dark:text-gray-100">
                          {att.title}
                        </div>
                        <div className="text-[11px] text-gray-500 dark:text-gray-400 flex items-center gap-2 mt-0.5">
                          <span>{att.subject_code}</span>
                          <span>•</span>
                          <span>{att.difficulty}</span>
                          <span>•</span>
                          <span>{new Date(att.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        {att.status === 'COMPLETED' ? (
                          <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                            {att.score}/{att.max_score} ({att.percentage}%)
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                            Incomplete
                          </span>
                        )}

                        <button
                          onClick={() => handleViewPastAttempt(att.id)}
                          className="px-2.5 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          View Results →
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ACTIVE QUIZ TAKING INTERFACE */}
          {activeQuiz && (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm transition-colors">
              {/* Quiz Stepper & Progress */}
              <div className="flex justify-between items-center pb-4 mb-4 border-b border-gray-100 dark:border-gray-800">
                <div>
                  <h3 className="text-base font-bold text-gray-900 dark:text-white">
                    {activeQuiz.title}
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    Question {currentQuestionIndex + 1} of {activeQuiz.questions.length} •{' '}
                    <span className="capitalize">{activeQuiz.difficulty}</span>
                  </p>
                </div>

                <div className="text-xs font-semibold px-2.5 py-1 rounded bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
                  Answered: {Object.keys(studentAnswers).length}/{activeQuiz.questions.length}
                </div>
              </div>

              {/* Current Question */}
              {(() => {
                const q = activeQuiz.questions[currentQuestionIndex]
                const selectedOption = studentAnswers[String(q.question_id)]

                return (
                  <div className="space-y-4">
                    <div className="text-sm sm:text-base font-semibold text-gray-900 dark:text-white leading-relaxed">
                      {currentQuestionIndex + 1}. {q.question}
                    </div>

                    {/* Options list */}
                    <div className="space-y-2.5 pt-2">
                      {q.options.map((opt, optIdx) => {
                        const isSelected = selectedOption === optIdx
                        return (
                          <div
                            key={optIdx}
                            onClick={() => handleSelectOption(q.question_id, optIdx)}
                            className={`p-3.5 rounded-xl border text-xs sm:text-sm cursor-pointer transition-all flex items-center gap-3 ${
                              isSelected
                                ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-500 dark:border-blue-500 text-blue-900 dark:text-blue-200 shadow-sm'
                                : 'bg-gray-50 dark:bg-gray-800/60 border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'
                            }`}
                          >
                            <div
                              className={`w-5 h-5 rounded-full border flex items-center justify-center text-xs font-semibold ${
                                isSelected
                                  ? 'border-blue-600 bg-blue-600 text-white'
                                  : 'border-gray-300 dark:border-gray-600 text-gray-500'
                              }`}
                            >
                              {String.fromCharCode(65 + optIdx)}
                            </div>
                            <span className="flex-1">{opt}</span>
                          </div>
                        )
                      })}
                    </div>

                    {/* Stepper Controls */}
                    <div className="flex justify-between items-center pt-6 mt-6 border-t border-gray-100 dark:border-gray-800">
                      <button
                        onClick={() => setCurrentQuestionIndex((prev) => Math.max(0, prev - 1))}
                        disabled={currentQuestionIndex === 0}
                        className="px-4 py-2 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
                      >
                        ← Previous
                      </button>

                      <div className="flex items-center gap-1.5">
                        {activeQuiz.questions.map((_, dotIdx) => {
                          const isAnswered = studentAnswers[String(activeQuiz.questions[dotIdx].question_id)] !== undefined
                          const isCurrent = dotIdx === currentQuestionIndex
                          return (
                            <button
                              key={dotIdx}
                              onClick={() => setCurrentQuestionIndex(dotIdx)}
                              className={`w-6 h-6 rounded-md text-[11px] font-semibold transition-all ${
                                isCurrent
                                  ? 'bg-blue-600 text-white shadow-sm'
                                  : isAnswered
                                  ? 'bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300'
                                  : 'bg-gray-100 dark:bg-gray-800 text-gray-400'
                              }`}
                            >
                              {dotIdx + 1}
                            </button>
                          )
                        })}
                      </div>

                      {currentQuestionIndex < activeQuiz.questions.length - 1 ? (
                        <button
                          onClick={() => setCurrentQuestionIndex((prev) => Math.min(activeQuiz.questions.length - 1, prev + 1))}
                          className="px-4 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-all"
                        >
                          Next →
                        </button>
                      ) : (
                        <button
                          onClick={handleSubmitQuiz}
                          disabled={isSubmittingQuiz}
                          className="px-5 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg shadow-sm transition-all flex items-center gap-1"
                        >
                          {isSubmittingQuiz ? 'Submitting...' : 'Submit Quiz ✓'}
                        </button>
                      )}
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          {/* QUIZ RESULT BREAKDOWN CARD */}
          {quizResult && !activeQuiz && (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm transition-colors space-y-6">
              {/* Score Banner */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-4 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 border border-blue-200 dark:border-blue-900 gap-4">
                <div>
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                    {quizResult.title}
                  </h3>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                    Submitted on {new Date(quizResult.submitted_at || Date.now()).toLocaleString()}
                  </p>
                </div>

                <div className="text-right">
                  <div className="text-2xl font-black text-blue-600 dark:text-blue-400">
                    {quizResult.score} / {quizResult.max_score}
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                    {quizResult.percentage}% Score
                  </span>
                </div>
              </div>

              {/* Question-by-Question Review */}
              <div className="space-y-4">
                <h4 className="text-sm font-bold text-gray-900 dark:text-white">
                  Detailed Question Review ({quizResult.questions_results.length})
                </h4>

                {quizResult.questions_results.map((qr, qrIdx) => {
                  const isCitExpanded = !!expandedQuizCitations[qr.question_id]

                  return (
                    <div
                      key={qr.question_id}
                      className={`p-4 rounded-xl border transition-colors ${
                        qr.is_correct
                          ? 'bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/50'
                          : 'bg-red-50/40 dark:bg-red-950/20 border-red-200 dark:border-red-900/50'
                      }`}
                    >
                      {/* Question Header & Status */}
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="font-semibold text-xs sm:text-sm text-gray-900 dark:text-white">
                          {qrIdx + 1}. {qr.question}
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[11px] font-semibold flex items-center gap-1 ${
                            qr.is_correct
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                              : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                          }`}
                        >
                          {qr.is_correct ? '✓ Correct' : '✗ Incorrect'}
                        </span>
                      </div>

                      {/* Options review */}
                      <div className="space-y-1.5 mb-3">
                        {qr.options.map((opt, oIdx) => {
                          const isSelected = qr.selected_option_index === oIdx
                          const isCorrectOpt = qr.correct_option_index === oIdx

                          let optClass = 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700'
                          if (isCorrectOpt) {
                            optClass = 'bg-emerald-100/70 dark:bg-emerald-950/70 text-emerald-900 dark:text-emerald-200 border-emerald-400 font-medium'
                          } else if (isSelected && !qr.is_correct) {
                            optClass = 'bg-red-100/70 dark:bg-red-950/70 text-red-900 dark:text-red-200 border-red-400 font-medium'
                          }

                          return (
                            <div
                              key={oIdx}
                              className={`p-2.5 rounded-lg border text-xs flex items-center justify-between gap-2 ${optClass}`}
                            >
                              <div className="flex items-center gap-2">
                                <span className="font-bold">{String.fromCharCode(65 + oIdx)}.</span>
                                <span>{opt}</span>
                              </div>
                              {isCorrectOpt && (
                                <span className="text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
                                  Correct Answer ✓
                                </span>
                              )}
                              {isSelected && !isCorrectOpt && (
                                <span className="text-[10px] font-semibold text-red-700 dark:text-red-300">
                                  Your Choice ✗
                                </span>
                              )}
                            </div>
                          )
                        })}
                      </div>

                      {/* Explanation */}
                      {qr.explanation && (
                        <div className="mt-2.5 p-3 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-xs text-gray-700 dark:text-gray-300">
                          <p className="font-semibold text-blue-600 dark:text-blue-400 mb-0.5">
                            💡 Syllabus Explanation:
                          </p>
                          <p className="whitespace-pre-wrap">{qr.explanation}</p>

                          {/* Source citation */}
                          {qr.citation && (
                            <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-800 flex flex-wrap items-center justify-between text-[11px] text-gray-500">
                              <span>
                                Source: {qr.citation.subject_code} Unit {qr.citation.unit_number || '1'} (Topic: {qr.citation.topic_title || 'Core'})
                              </span>
                              {qr.citation.source_evidence && (
                                <button
                                  onClick={() =>
                                    setExpandedQuizCitations((p) => ({
                                      ...p,
                                      [qr.question_id]: !p[qr.question_id]
                                    }))
                                  }
                                  className="text-blue-500 hover:underline"
                                >
                                  {isCitExpanded ? 'Hide passage' : 'View verified snippet'}
                                </button>
                              )}
                            </div>
                          )}

                          {isCitExpanded && qr.citation?.source_evidence && (
                            <p className="mt-2 text-[11px] italic text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 p-2 rounded border border-gray-200 dark:border-gray-700">
                              "{qr.citation.source_evidence}"
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Action */}
              <div className="flex justify-end pt-4 border-t border-gray-200 dark:border-gray-800">
                <button
                  onClick={() => setQuizResult(null)}
                  className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-all"
                >
                  Done Reviewing
                </button>
              </div>
            </div>
          )}

          {/* Empty / Welcome State */}
          {!activeQuiz && !quizResult && (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-12 text-center shadow-sm transition-colors">
              <span className="text-4xl mb-3 block">🎯</span>
              <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">
                Select your subject and parameters to start a quiz
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                Questions are synthesized directly from approved institutional syllabus documents with verified source citations.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default StudyBuddy
