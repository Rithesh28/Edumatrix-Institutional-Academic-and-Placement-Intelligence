import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, MapPin, Globe, Mail, Phone, Edit2, Trash2 } from 'lucide-react';

const CompanyCard = ({ company, onDelete }) => {
  const navigate = useNavigate();

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
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
            <p className="text-sm text-gray-400 flex items-center space-x-1 mt-1">
              <MapPin className="w-3 h-3" />
              <span>{company.location}</span>
            </p>
          )}
          {company.website && (
            <a
              href={company.website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-indigo-600 hover:text-indigo-800 flex items-center space-x-1 mt-1"
            >
              <Globe className="w-3 h-3" />
              <span>{company.website}</span>
            </a>
          )}
          <div className="flex flex-wrap gap-2 mt-2">
            {company.contact_email && (
              <span className="text-xs text-gray-500 flex items-center space-x-1">
                <Mail className="w-3 h-3" />
                <span>{company.contact_email}</span>
              </span>
            )}
            {company.contact_phone && (
              <span className="text-xs text-gray-500 flex items-center space-x-1">
                <Phone className="w-3 h-3" />
                <span>{company.contact_phone}</span>
              </span>
            )}
          </div>
          <div className="mt-2">
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
            onClick={() => onDelete?.(company.id)}
            className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default CompanyCard;