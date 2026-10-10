import React, { useState, useEffect } from 'react'
import { certificationAPI } from '../services/api'
import toast from 'react-hot-toast'

const CertificationUpload = () => {
  const [certifications, setCertifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    issuer: '',
    credential_id: '',
    issue_date: '',
    expiry_date: ''
  })

  const fetchCertifications = async () => {
    try {
      const response = await certificationAPI.getAll()
      setCertifications(response.data)
    } catch (error) {
      console.error('Failed to fetch certifications:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCertifications()
  }, [])

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const response = await certificationAPI.add(formData)
      setCertifications([...certifications, response.data])
      setFormData({ name: '', issuer: '', credential_id: '', issue_date: '', expiry_date: '' })
      setShowForm(false)
      toast.success('Certification added successfully')
    } catch (error) {
      toast.error('Failed to add certification')
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this certification?')) return

    try {
      await certificationAPI.delete(id)
      setCertifications(certifications.filter(c => c.id !== id))
      toast.success('Certification deleted successfully')
    } catch (error) {
      toast.error('Failed to delete certification')
    }
  }

  if (loading) {
    return <div className="text-center py-4">Loading certifications...</div>
  }

  return (
    <div>
      <button
        onClick={() => setShowForm(!showForm)}
        className="mb-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        {showForm ? 'Cancel' : '+ Add Certification'}
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-4 p-4 bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700 rounded-lg space-y-3">
          <div>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="Certification Name"
              required
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <input
              type="text"
              name="issuer"
              value={formData.issuer}
              onChange={handleChange}
              placeholder="Issuing Organization"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <input
              type="text"
              name="credential_id"
              value={formData.credential_id}
              onChange={handleChange}
              placeholder="Credential ID (Optional)"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-300">Issue Date</label>
              <input
                type="date"
                name="issue_date"
                value={formData.issue_date}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-300">Expiry Date</label>
              <input
                type="date"
                name="expiry_date"
                value={formData.expiry_date}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <button
            type="submit"
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Add Certification
          </button>
        </form>
      )}

      {/* Certifications List */}
      <div className="space-y-2">
        {certifications.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-sm">No certifications added yet</p>
        ) : (
          certifications.map((cert) => (
            <div
              key={cert.id}
              className="flex justify-between items-center p-3 border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/40 rounded-lg"
            >
              <div>
                <p className="font-medium text-gray-900 dark:text-gray-100">{cert.name}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">{cert.issuer}</p>
                {cert.issue_date && (
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    Issued: {new Date(cert.issue_date).toLocaleDateString()}
                  </p>
                )}
              </div>
              <button
                onClick={() => handleDelete(cert.id)}
                className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 text-sm cursor-pointer"
              >
                Delete
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default CertificationUpload