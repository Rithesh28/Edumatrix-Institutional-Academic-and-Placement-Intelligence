import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  Trash2,
  Edit2,
  File,
  Calendar,
  User,
  Tag,
  Folder,
  Copy,
} from 'lucide-react';
import { format } from 'date-fns';
import useFileStore from '../store/fileStore';
import FilePreview from '../components/FilePreview';
import FileVersionHistory from '../components/FileVersionHistory';

const FileDetail = () => {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const { selectedFile, isLoading, error, getFileDetails, downloadFile, deleteFile, updateFile } = useFileStore();
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});

  useEffect(() => {
    if (fileId) {
      getFileDetails(fileId);
    }
  }, [fileId]);

  useEffect(() => {
    if (selectedFile) {
      setEditData({
        title: selectedFile.title || '',
        description: selectedFile.description || '',
        tags: selectedFile.tags || [],
        department: selectedFile.department || '',
        file_type: selectedFile.file_type || '',
      });
    }
  }, [selectedFile]);

  const handleDownload = async () => {
    if (selectedFile) {
      await downloadFile(selectedFile.id, selectedFile.filename);
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this file?')) {
      await deleteFile(fileId);
      navigate('/files');
    }
  };

  const handleUpdate = async () => {
    await updateFile(fileId, editData);
    setIsEditing(false);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          {error}
        </div>
      </div>
    );
  }

  if (!selectedFile) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-gray-500">File not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Back Button */}
      <button
        onClick={() => navigate('/files')}
        className="flex items-center space-x-2 text-gray-600 hover:text-gray-800 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Files</span>
      </button>

      {/* File Info */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-gray-100 rounded-lg">
              <File className="w-8 h-8 text-gray-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {selectedFile.title || selectedFile.filename}
              </h1>
              <p className="text-sm text-gray-500">{selectedFile.filename}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="px-3 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg"
            >
              <Edit2 className="w-4 h-4" />
            </button>
            <button
              onClick={handleDownload}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              <Download className="w-4 h-4 inline mr-2" />
              Download
            </button>
            <button
              onClick={handleDelete}
              className="px-3 py-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Metadata */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-gray-500">File Type</p>
            <p className="text-sm font-medium text-gray-900 capitalize">
              {selectedFile.file_type?.replace('_', ' ')}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Size</p>
            <p className="text-sm font-medium text-gray-900">
              {Math.round(selectedFile.file_size / 1024)} KB
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Department</p>
            <p className="text-sm font-medium text-gray-900">{selectedFile.department}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Uploaded</p>
            <p className="text-sm font-medium text-gray-900">
              {selectedFile.created_at ? format(new Date(selectedFile.created_at), 'PPp') : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Version</p>
            <p className="text-sm font-medium text-gray-900">v{selectedFile.version}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Status</p>
            <p className="text-sm font-medium text-gray-900 capitalize">{selectedFile.status}</p>
          </div>
        </div>

        {/* Description */}
        {selectedFile.description && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-700">{selectedFile.description}</p>
          </div>
        )}

        {/* Tags */}
        {selectedFile.tags && selectedFile.tags.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {selectedFile.tags.map((tag) => (
              <span key={tag} className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Edit Form */}
      {isEditing && (
        <div className="mt-4 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Edit File</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Title</label>
              <input
                type="text"
                value={editData.title || ''}
                onChange={(e) => setEditData({ ...editData, title: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Description</label>
              <textarea
                value={editData.description || ''}
                onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div className="flex space-x-2">
              <button
                onClick={handleUpdate}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                Save Changes
              </button>
              <button
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 rounded-lg"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Preview */}
      <div className="mt-4">
        <FilePreview fileId={selectedFile.id} />
      </div>

      {/* Version History */}
      <div className="mt-4">
        <FileVersionHistory fileId={selectedFile.id} />
      </div>
    </div>
  );
};

export default FileDetail;