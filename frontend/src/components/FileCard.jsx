import React from 'react';
import { Link } from 'react-router-dom';
import {
  File,
  FileText,
  Image,
  Table,
  Presentation,
  Archive,
  Download,
  Trash2,
  Edit2,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const getFileIcon = (mimeType, filename) => {
  if (!mimeType) return <File className="w-8 h-8 text-gray-400" />;
  
  if (mimeType.startsWith('image/')) {
    return <Image className="w-8 h-8 text-purple-500" />;
  }
  if (mimeType === 'application/pdf') {
    return <FileText className="w-8 h-8 text-red-500" />;
  }
  if (mimeType.includes('word') || mimeType.includes('document')) {
    return <FileText className="w-8 h-8 text-blue-500" />;
  }
  if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) {
    return <Table className="w-8 h-8 text-green-500" />;
  }
  if (mimeType.includes('presentation') || mimeType.includes('powerpoint')) {
    return <Presentation className="w-8 h-8 text-orange-500" />;
  }
  if (mimeType.includes('zip') || mimeType.includes('rar') || mimeType.includes('archive')) {
    return <Archive className="w-8 h-8 text-gray-500" />;
  }
  return <File className="w-8 h-8 text-gray-400" />;
};

const getFileTypeColor = (fileType) => {
  const colors = {
    exam_duty: 'bg-purple-100 text-purple-700',
    assignment: 'bg-blue-100 text-blue-700',
    circular: 'bg-green-100 text-green-700',
    resume: 'bg-pink-100 text-pink-700',
    timetable: 'bg-yellow-100 text-yellow-700',
    certificate: 'bg-indigo-100 text-indigo-700',
    placement_doc: 'bg-cyan-100 text-cyan-700',
    other: 'bg-gray-100 text-gray-700',
  };
  return colors[fileType] || colors.other;
};

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const FileCard = ({ file, onDelete, onDownload, onEdit }) => {
  const { id, filename, title, file_type, file_size, mime_type, created_at, department } = file;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow p-4">
      <div className="flex items-start space-x-4">
        {/* Icon */}
        <div className="flex-shrink-0">
          {getFileIcon(mime_type, filename)}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <Link to={`/files/${id}`} className="block hover:underline">
            <h3 className="text-sm font-medium text-gray-900 truncate">
              {title || filename}
            </h3>
          </Link>
          
          <div className="flex items-center space-x-2 mt-1">
            <span className="text-xs text-gray-500 truncate">{filename}</span>
            <span className="text-xs text-gray-400">•</span>
            <span className="text-xs text-gray-500">{formatFileSize(file_size)}</span>
          </div>

          <div className="flex items-center space-x-2 mt-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${getFileTypeColor(file_type)}`}>
              {file_type.replace('_', ' ')}
            </span>
            {department && (
              <span className="text-xs text-gray-500">{department}</span>
            )}
            {created_at && (
              <span className="text-xs text-gray-400">
                {formatDistanceToNow(new Date(created_at), { addSuffix: true })}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-1">
          <button
            onClick={() => onDownload?.(id, filename)}
            className="p-1.5 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100"
            title="Download"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit?.(id)}
            className="p-1.5 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100"
            title="Edit"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete?.(id)}
            className="p-1.5 text-gray-400 hover:text-red-600 rounded-full hover:bg-red-50"
            title="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default FileCard;