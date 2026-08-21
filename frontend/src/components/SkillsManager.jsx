import React, { useState, useEffect } from 'react'
import { profileAPI } from '../services/api'
import toast from 'react-hot-toast'

const SkillsManager = () => {
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)
  const [newSkill, setNewSkill] = useState({ name: '', proficiency: 'intermediate' })
  const [editingId, setEditingId] = useState(null)

  const fetchSkills = async () => {
    try {
      const response = await profileAPI.getSkills()
      setSkills(response.data)
    } catch (error) {
      console.error('Failed to fetch skills:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSkills()
  }, [])

  const handleAddSkill = async (e) => {
    e.preventDefault()
    if (!newSkill.name.trim()) {
      toast.error('Skill name is required')
      return
    }

    try {
      const response = await profileAPI.addSkill(newSkill)
      setSkills([...skills, response.data])
      setNewSkill({ name: '', proficiency: 'intermediate' })
      toast.success('Skill added successfully')
    } catch (error) {
      toast.error('Failed to add skill')
    }
  }

  const handleDeleteSkill = async (id) => {
    if (!window.confirm('Are you sure you want to delete this skill?')) return

    try {
      await profileAPI.deleteSkill(id)
      setSkills(skills.filter(s => s.id !== id))
      toast.success('Skill deleted successfully')
    } catch (error) {
      toast.error('Failed to delete skill')
    }
  }

  const getProficiencyColor = (level) => {
    const colors = {
      beginner: 'bg-blue-100 text-blue-700',
      intermediate: 'bg-yellow-100 text-yellow-700',
      advanced: 'bg-orange-100 text-orange-700',
      expert: 'bg-green-100 text-green-700'
    }
    return colors[level] || 'bg-gray-100 text-gray-700'
  }

  if (loading) {
    return <div className="text-center py-4">Loading skills...</div>
  }

  return (
    <div>
      {/* Add Skill Form */}
      <form onSubmit={handleAddSkill} className="flex gap-2 mb-4">
        <input
          type="text"
          value={newSkill.name}
          onChange={(e) => setNewSkill({ ...newSkill, name: e.target.value })}
          placeholder="Enter skill (e.g., Python)"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={newSkill.proficiency}
          onChange={(e) => setNewSkill({ ...newSkill, proficiency: e.target.value })}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="beginner">Beginner</option>
          <option value="intermediate">Intermediate</option>
          <option value="advanced">Advanced</option>
          <option value="expert">Expert</option>
        </select>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Add
        </button>
      </form>

      {/* Skills List */}
      <div className="flex flex-wrap gap-2">
        {skills.length === 0 ? (
          <p className="text-gray-500 text-sm">No skills added yet</p>
        ) : (
          skills.map((skill) => (
            <div
              key={skill.id}
              className="flex items-center gap-2 px-3 py-1 bg-gray-100 rounded-full"
            >
              <span className="font-medium text-gray-800">{skill.name}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${getProficiencyColor(skill.proficiency)}`}>
                {skill.proficiency}
              </span>
              <button
                onClick={() => handleDeleteSkill(skill.id)}
                className="text-red-500 hover:text-red-700 text-sm"
              >
                ×
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default SkillsManager