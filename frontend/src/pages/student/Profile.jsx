import React, { useState, useEffect } from 'react'
import { profileAPI } from '../../services/api'
import ProfileForm from '../../components/ProfileForm'
import SkillsManager from '../../components/SkillsManager'
import ResumeUpload from '../../components/ResumeUpload'
import CertificationUpload from '../../components/CertificationUpload'
import StudentVerifiedOfferCard from '../../components/placement/StudentVerifiedOfferCard'
import StudentRecruitmentTimeline from '../../components/placement/StudentRecruitmentTimeline'
import usePlacementStore from '../../store/placementStore'
import { useAuthStore } from '../../store/authStore'
import { Award, TrendingUp, ShieldCheck, CheckCircle2, Clock } from 'lucide-react'
import toast from 'react-hot-toast'

const Profile = () => {
  const { user } = useAuthStore()
  const {
    myOffers,
    isMyOffersLoading,
    fetchMyOffers,
    myPlacementStatus,
    fetchMyPlacementStatus,
  } = usePlacementStore()

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
    if (user?.id) {
      fetchMyOffers().catch(() => {})
      fetchMyPlacementStatus(user.id).catch(() => {})
    }
  }, [user?.id])

  if (loading) {
    return <div className="text-center py-10">Loading profile...</div>
  }

  const effectivePlacementStatus =
    myPlacementStatus?.status || profile?.placement_status || 'not_applied'

  const getStatusBadge = (s) => {
    switch (s?.toLowerCase()) {
      case 'placed':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5" />
            PLACED
          </span>
        )
      case 'selected':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-purple-100 dark:bg-purple-950/70 text-purple-800 dark:text-purple-300 border border-purple-300 dark:border-purple-800">
            SELECTED
          </span>
        )
      case 'applied':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-blue-100 dark:bg-blue-950/70 text-blue-800 dark:text-blue-300 border border-blue-300 dark:border-blue-800">
            <Clock className="w-3.5 h-3.5" />
            APPLIED
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-700">
            {s ? s.toUpperCase() : 'NOT APPLIED'}
          </span>
        )
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">My Profile</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Manage your personal profile, credentials, and placement recruitment progress.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Placement Status:</span>
          {getStatusBadge(effectivePlacementStatus)}
        </div>
      </div>

      <div className="flex border-b border-gray-200 dark:border-gray-800 overflow-x-auto">
        {[
          { id: 'personal', label: 'Personal Info' },
          { id: 'skills', label: 'Skills' },
          { id: 'certifications', label: 'Certifications' },
          { id: 'resume', label: 'Resumes' },
          { id: 'placement', label: 'Offers & Progression' },
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
        {activeTab === 'placement' && (
          <div className="space-y-8">
            {/* Verified Placement Offers */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-950/70 text-emerald-600 dark:text-emerald-400">
                  <Award className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-base font-bold text-gray-900 dark:text-white">
                    Verified Placement Offers ({myOffers.length})
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Official employment offers extended to you following Placement Cell verification.
                  </p>
                </div>
              </div>

              {isMyOffersLoading && myOffers.length === 0 ? (
                <div className="p-6 text-center text-xs text-gray-500">Loading verified offers...</div>
              ) : myOffers.length === 0 ? (
                <div className="p-6 text-center rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30 text-xs text-gray-500">
                  No verified placement offers have been issued yet. Complete recruitment rounds to qualify for offers.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {myOffers.map((offer) => (
                    <StudentVerifiedOfferCard
                      key={offer.id}
                      offer={offer}
                      onOfferUpdated={() => {
                        fetchMyOffers().catch(() => {})
                        if (user?.id) fetchMyPlacementStatus(user.id).catch(() => {})
                      }}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Inline Recruitment Round Progression Timeline */}
            <div className="space-y-3 pt-6 border-t border-gray-100 dark:border-gray-800">
              <StudentRecruitmentTimeline
                studentId={user?.id}
                inline={true}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Profile