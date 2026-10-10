import React, { useState, useEffect } from 'react'
import { profileAPI } from '../../services/api'
import ProfileForm from '../../components/ProfileForm'
import SkillsManager from '../../components/SkillsManager'
import ResumeUpload from '../../components/ResumeUpload'
import CertificationUpload from '../../components/CertificationUpload'
import toast from 'react-hot-toast'

const Profile = () => {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('personal')

  const fetchProfile = async () => {
    try {
      const response = await profileAPI.getProfile()
      setProfile(response.data)
    } catch (error) {
      console.error('Failed to fetch profile:', error)
      toast.error('Failed to load profile')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProfile()
  }, [])

  if (loading) {
    return <div className="text-center py-10">Loading profile...</div>
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">My Profile</h1>

      <div className="flex border-b border-gray-200 dark:border-gray-800 mb-6 overflow-x-auto">
        {[
          { id: 'personal', label: 'Personal Info' },
          { id: 'skills', label: 'Skills' },
          { id: 'certifications', label: 'Certifications' },
          { id: 'resume', label: 'Resumes' }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap cursor-pointer ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 font-semibold'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
        {activeTab === 'personal' && <ProfileForm profile={profile} onUpdate={setProfile} />}
        {activeTab === 'skills' && <SkillsManager />}
        {activeTab === 'certifications' && <CertificationUpload />}
        {activeTab === 'resume' && <ResumeUpload />}
      </div>
    </div>
  )
}

export default Profile