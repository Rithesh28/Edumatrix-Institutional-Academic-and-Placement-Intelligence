import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, Plus, Search, Edit2, Trash2, ExternalLink, ArrowLeft } from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const Companies = () => {
  const navigate = useNavigate();
  const { companies, isLoading, fetchCompanies, deleteCompany } = usePlacementStore();
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchCompanies();
  }, []);

  const handleDelete = async (id, name) => {
    if (window.confirm(`Are you sure you want to delete "${name}"?`)) {
      try {
        await deleteCompany(id);
        toast.success('Company deleted successfully');
      } catch (error) {
        toast.error('Failed to delete company');
      }
    }
  };

  const filteredCompanies = companies.filter((c) =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.industry?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div>
      {/* Back Button */}
      <button
        onClick={() => navigate('/placement/dashboard')}
        className="flex items-center space-x-2 text-gray-600 hover:text-gray-800 mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Dashboard</span>
      </button>

      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Companies</h1>
          <p className="text-gray-500 text-sm">Manage partner companies and recruiters</p>
        </div>
        <button
          onClick={() => navigate('/placement/companies/add')}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center space-x-2"
        >
          <Plus className="w-4 h-4" />
          <span>Add Company</span>
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search companies..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        />
      </div>

      {/* Companies Grid */}
      {filteredCompanies.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <Building2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No companies found</p>
          <button
            onClick={() => navigate('/placement/companies/add')}
            className="mt-2 text-indigo-600 hover:text-indigo-800"
          >
            Add your first company
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCompanies.map((company) => (
            <div
              key={company.id}
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <Building2 className="w-5 h-5 text-indigo-500" />
                    <h3 className="font-semibold text-gray-900">{company.name}</h3>
                  </div>
                  {company.industry && (
                    <p className="text-sm text-gray-500 mt-1">{company.industry}</p>
                  )}
                  {company.location && (
                    <p className="text-sm text-gray-400">{company.location}</p>
                  )}
                  {company.website && (
                    <a
                      href={company.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-indigo-600 hover:text-indigo-800 flex items-center space-x-1 mt-1"
                    >
                      <span>{company.website}</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                  <div className="flex items-center space-x-2 mt-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      company.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {company.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
                <div className="flex space-x-1">
                  <button
                    onClick={() => navigate(`/placement/companies/${company.id}/edit`)}
                    className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(company.id, company.name)}
                    className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {company.contact_email && (
                <p className="text-xs text-gray-400 mt-2">📧 {company.contact_email}</p>
              )}
              {company.contact_phone && (
                <p className="text-xs text-gray-400">📞 {company.contact_phone}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Companies;